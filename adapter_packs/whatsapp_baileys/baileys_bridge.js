const { makeWASocket, useMultiFileAuthState, DisconnectReason, Browsers, fetchLatestBaileysVersion } = require('@whiskeysockets/baileys');
const { Boom } = require('@hapi/boom');
const pino = require('pino');
const express = require('express');
const qrcode = require('qrcode-terminal');

const PORT = process.env.BRIDGE_PORT || 3001;
const SESSION_NAME = process.env.SESSION_NAME || 'default';
const SESSION_DIR = `baileys_session_${SESSION_NAME}`;

let sock = null;
let status = 'INITIALIZING';
let incomingMessages = [];

async function connectToWhatsApp() {
    const { state, saveCreds } = await useMultiFileAuthState(SESSION_DIR);
    const { version, isLatest } = await fetchLatestBaileysVersion();
    console.log(`[BaileysBridge] Using WhatsApp Web version v${version.join('.')}, isLatest: ${isLatest}`);
    
    sock = makeWASocket({
        auth: state,
        version: version,
        browser: Browsers.ubuntu('Chrome'),
        printQRInTerminal: false,
        logger: pino({ level: 'silent' }) // suppress verbose logs
    });

    sock.ev.on('connection.update', (update) => {
        const { connection, lastDisconnect, qr } = update;
        if (qr) {
            status = 'SCAN_QR_CODE';
            console.log('\n[BaileysBridge] Scan this barcode to log in:');
            qrcode.generate(qr, { small: true });
        }
        if (connection === 'close') {
            const error = lastDisconnect.error;
            const statusCode = (error instanceof Boom)?.output?.statusCode || error?.output?.statusCode;
            const shouldReconnect = statusCode !== DisconnectReason.loggedOut;
            
            console.log(`[BaileysBridge] Connection closed. Reason: ${error}. Status: ${statusCode}. Reconnecting: ${shouldReconnect}`);
            
            status = 'DISCONNECTED';
            if (shouldReconnect) {
                setTimeout(connectToWhatsApp, 5000); // Wait 5s before reconnecting
            }
        } else if (connection === 'open') {
            status = 'WORKING';
            console.log('[BaileysBridge] Connection opened! Ready to proxy messages.');
        }
    });

    sock.ev.on('creds.update', saveCreds);

    sock.ev.on('messages.upsert', async (m) => {
        if (m.type !== 'notify') return;
        
        for (const msg of m.messages) {
            if (msg.key.fromMe) continue;
            const remoteJid = msg.key.remoteJid;
            const messageId = msg.key.id;
            const text = msg.message?.conversation || msg.message?.extendedTextMessage?.text || '';
            const timestamp = msg.messageTimestamp;
            
            // Extract sender (if group, who sent it. if DM, it's the remoteJid)
            const senderJid = msg.key.participant || remoteJid;

            if (text.trim() === '') continue; // Skip non-text or empty text messages
            
            incomingMessages.push({
                id: messageId,
                from: remoteJid,
                sender: senderJid,
                body: text,
                timestamp: timestamp
            });
            
            // Mark as read immediately to avoid clutter
            try {
                await sock.readMessages([msg.key]);
            } catch (err) {
                // Ignore read failures
            }
        }
    });
}

connectToWhatsApp();

const app = express();
app.use(express.json());

// API Endpoints for the Python Adapter
app.get('/status', (req, res) => {
    res.json({ status });
});

app.get('/messages', (req, res) => {
    // Return all incoming and clear the buffer
    const msgs = [...incomingMessages];
    incomingMessages = [];
    res.json({ messages: msgs });
});

app.post('/send', async (req, res) => {
    if (status !== 'WORKING' || !sock) {
        return res.status(400).json({ error: 'Not connected' });
    }
    const { to, text } = req.body;
    try {
        await sock.sendMessage(to, { text });
        res.json({ success: true });
    } catch (err) {
        res.status(500).json({ error: err.toString() });
    }
});

app.listen(PORT, '127.0.0.1', () => {
    console.log(`[BaileysBridge] HTTP API internal server listening on port ${PORT}`);
});
