import { useState, useCallback, useRef, useEffect } from 'react';
import { useWebRTCSession } from '../hooks/useWebRTCSession';

const agentRuntimeArn = import.meta.env.VITE_AGENT_RUNTIME_ARN;

export default function VoiceChat() {
  const [isActive, setIsActive] = useState(false);
  const [connectionError, setConnectionError] = useState('');
  const transcriptEndRef = useRef(null);

  const { status, transcripts, connect, disconnect } = useWebRTCSession({
    agentRuntimeArn: agentRuntimeArn || undefined,
  });

  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [transcripts]);

  const handleToggle = async () => {
    if (status === 'connecting') return;

    if (isActive) {
      await disconnect();
      setIsActive(false);
      setConnectionError('');
    } else {
      setConnectionError('');
      try {
        await connect();
        setIsActive(true);
      } catch (err) {
        setIsActive(false);
        setConnectionError(err?.message || 'Unable to connect to the voice agent');
      }
    }
  };

  const statusText = connectionError
    ? `Connection failed: ${connectionError}`
    : status === 'connecting'
      ? 'Connecting...'
      : status === 'connected'
        ? 'Listening - speak to ask a question'
        : isActive
          ? 'Starting...'
          : 'Click the microphone to start';

  return (
    <div style={styles.wrapper}>
      <button
        onClick={handleToggle}
        style={{
          ...styles.micButton,
          background: isActive ? '#c0392b' : '#2d5016',
          boxShadow: isActive
            ? '0 4px 16px rgba(192, 57, 43, 0.3)'
            : '0 4px 16px rgba(45, 80, 22, 0.3)',
        }}
        aria-label={isActive ? 'Stop voice session' : 'Start voice session'}
      >
        <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          {isActive ? (
            <rect x="6" y="6" width="12" height="12" rx="1" />
          ) : (
            <>
              <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
              <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
              <line x1="12" y1="19" x2="12" y2="23" />
              <line x1="8" y1="23" x2="16" y2="23" />
            </>
          )}
        </svg>
      </button>

      <p style={styles.status}>{statusText}</p>

      {transcripts.length > 0 && (
        <div style={styles.transcriptArea}>
          {transcripts.map((t, i) => (
            <div key={i} style={{ ...styles.transcript, alignSelf: t.role === 'user' ? 'flex-end' : 'flex-start' }}>
              <span style={styles.role}>{t.role === 'user' ? 'You' : 'Assistant'}</span>
              <div style={{ ...styles.bubble, ...(t.role === 'user' ? styles.userBubble : styles.botBubble) }}>
                {t.text}
              </div>
            </div>
          ))}
          <div ref={transcriptEndRef} />
        </div>
      )}

      {isActive && (
        <p style={styles.hint}>
          Say &quot;stop&quot; or &quot;goodbye&quot; to end the session.
          You can interrupt the assistant by speaking over it.
        </p>
      )}
    </div>
  );
}

const styles = {
  wrapper: { display: 'flex', flexDirection: 'column', alignItems: 'center', width: '100%' },
  micButton: {
    width: 80, height: 80, borderRadius: '50%', border: 'none', cursor: 'pointer',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    transition: 'all 0.2s ease', marginBottom: '1rem',
  },
  status: { fontSize: '0.9rem', color: '#666666', marginBottom: '0.5rem' },
  transcriptArea: {
    display: 'flex', flexDirection: 'column', gap: '0.75rem', width: '100%',
    maxHeight: 400, overflowY: 'auto', marginTop: '1.5rem', padding: '0 0.5rem',
  },
  transcript: { maxWidth: '85%' },
  role: { fontSize: '0.7rem', color: '#666666', textTransform: 'uppercase', letterSpacing: '0.05em', display: 'block', marginBottom: '0.15rem' },
  bubble: { fontSize: '0.9rem', lineHeight: 1.4, padding: '0.6rem 0.85rem', borderRadius: '12px' },
  userBubble: { background: '#2d5016', color: '#ffffff', borderBottomRightRadius: '4px' },
  botBubble: { background: '#ffffff', color: '#1a1a1a', border: '1px solid #e0e0d8', boxShadow: '0 1px 3px rgba(0, 0, 0, 0.06)', borderBottomLeftRadius: '4px' },
  hint: { fontSize: '0.75rem', color: '#666666', textAlign: 'center', marginTop: '2rem', maxWidth: 320, lineHeight: 1.4 },
};
