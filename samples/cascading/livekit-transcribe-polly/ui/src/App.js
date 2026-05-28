import React, { useState, useEffect, useRef } from 'react';
import { LiveKitRoom, AudioConference, useRoomContext, useDataChannel } from '@livekit/components-react';
import '@livekit/components-styles';
import './App.css';

const TOKEN = process.env.REACT_APP_LIVEKIT_TOKEN;
const WS_URL = process.env.REACT_APP_LIVEKIT_SERVER_URL || "ws://localhost:7880";

function TranscriptionPanel() {
    const [messages, setMessages] = useState([]);
    const messagesEndRef = useRef(null);
    const room = useRoomContext();

    useEffect(() => {
        if (!room) return;

        const handleTranscription = (segments, participant) => {
            segments.forEach(segment => {
                if (!segment.text || !segment.final) return;

                const role = participant?.identity?.includes('agent') ? 'assistant' : 'user';
                setMessages(prev => [...prev, {
                    id: segment.id || Date.now() + Math.random(),
                    role,
                    text: segment.text,
                    timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
                }]);
            });
        };

        room.on('transcriptionReceived', handleTranscription);
        return () => room.off('transcriptionReceived', handleTranscription);
    }, [room]);

    const onDataReceived = (payload) => {
        try {
            const text = new TextDecoder().decode(payload);
            const data = JSON.parse(text);

            if (data.type === 'tool_call' || data.type === 'function_call') {
                setMessages(prev => [...prev, {
                    id: Date.now() + Math.random(),
                    role: 'tool',
                    text: `${data.name || data.function || 'unknown'}(${JSON.stringify(data.arguments || {})})`,
                    timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
                }]);
            }
        } catch (e) { /* ignore non-JSON */ }
    };

    useDataChannel(onDataReceived);

    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages]);

    return (
        <div className='transcription-panel'>
            <div className='panel-header'>
                <span className='live-dot'></span>
                Live Transcription
            </div>
            <div className='messages'>
                {messages.length === 0 && (
                    <div className='empty-state'>
                        🎤 Start speaking to see live transcriptions here.<br/>
                        Tool calls will also appear in real time.
                    </div>
                )}
                {messages.map((msg) => (
                    <div key={msg.id} className={`message message-${msg.role}`}>
                        <span className='message-icon'>
                            {msg.role === 'user' ? '🎤' : msg.role === 'tool' ? '🔧' : '🤖'}
                        </span>
                        <span className='message-text'>{msg.text}</span>
                        <span className='message-time'>{msg.timestamp}</span>
                    </div>
                ))}
                <div ref={messagesEndRef} />
            </div>
        </div>
    );
}

function App() {
    return (
        <div className='livekit'>
            <div className='header'>
                <div className='title'>🎙️ Voice Agent (Transcribe + Nova Lite + Polly)</div>
                <div className='subtitle'>Sandwich pipeline: STT → LLM → TTS via LiveKit</div>
                <div className='badges'>
                    <span className='badge badge-model'>Transcribe → Nova Lite → Polly</span>
                    <span className='badge badge-server'>{WS_URL}</span>
                </div>
            </div>

            <div className='main-content' data-lk-theme="default">
                <LiveKitRoom
                    audio={true}
                    video={false}
                    token={TOKEN}
                    serverUrl={WS_URL}
                    connect={true}
                >
                    <div className='layout'>
                        <div className='conference-container'>
                            <div className='panel-label'>Audio Controls</div>
                            <AudioConference />
                        </div>
                        <TranscriptionPanel />
                    </div>
                </LiveKitRoom>
            </div>

            <div className='footer'>
                Powered by <a href="https://docs.livekit.io/agents/" target="_blank" rel="noreferrer">LiveKit Agents</a> &amp; <a href="https://aws.amazon.com/transcribe/" target="_blank" rel="noreferrer">Amazon Transcribe</a> + <a href="https://aws.amazon.com/polly/" target="_blank" rel="noreferrer">Amazon Polly</a>
            </div>
        </div>
    );
}

export default App;
