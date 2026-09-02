import { useState, useRef, useCallback, useEffect } from 'react';
import { BedrockAgentCoreClient, InvokeAgentRuntimeCommand } from '@aws-sdk/client-bedrock-agentcore';
import { getAWSCredentials } from '../aws-credentials.js';

const region = import.meta.env.VITE_REGION || 'us-east-1';

/**
 * Manages a WebRTC session to the voice agent.
 *
 * Local mode: POST to /invocations via Vite proxy.
 * Deployed mode: Uses @aws-sdk/client-bedrock-agentcore with runtimeSessionId for session affinity.
 */
export function useWebRTCSession({ agentRuntimeArn } = {}) {
  const [status, setStatus] = useState('disconnected');
  const [transcripts, setTranscripts] = useState([]);
  const pcRef = useRef(null);
  const sessionIdRef = useRef(null);

  // Invoke the agent (local or deployed)
  const invoke = useCallback(async (action, data = {}) => {
    const payload = { action, data };

    if (agentRuntimeArn) {
      const creds = await getAWSCredentials();
      const client = new BedrockAgentCoreClient({
        region,
        credentials: {
          accessKeyId: creds.accessKeyId,
          secretAccessKey: creds.secretAccessKey,
          sessionToken: creds.sessionToken,
        },
      });
      const resp = await client.send(new InvokeAgentRuntimeCommand({
        agentRuntimeArn,
        runtimeSessionId: sessionIdRef.current,
        contentType: 'application/json',
        accept: 'application/json',
        payload: new TextEncoder().encode(JSON.stringify(payload)),
      }));
      return JSON.parse(new TextDecoder().decode(await resp.response.transformToByteArray()));
    }

    // Local mode
    const resp = await fetch('/invocations', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    return resp.json();
  }, [agentRuntimeArn]);

  const connect = useCallback(async () => {
    if (pcRef.current) return;
    setStatus('connecting');
    setTranscripts([]);
    sessionIdRef.current = crypto.randomUUID();

    try {
      // 1. Warmup: first call wakes the container, retry if it fails
      let iceServers;
      for (let attempt = 0; attempt < 3; attempt++) {
        try {
          const config = await invoke('ice_config');
          iceServers = config.iceServers || [];
          break;
        } catch (err) {
          if (attempt === 2) throw err;
          console.warn(`[WebRTC] ice_config attempt ${attempt + 1} failed, retrying...`);
          await new Promise((r) => setTimeout(r, 2000));
        }
      }

      // 2. Create peer connection
      const pc = new RTCPeerConnection({ iceServers });
      pcRef.current = pc;

      // 3. Queue ICE candidates until we have a pc_id
      const pendingCandidates = [];
      let canSend = false;

      pc.ontrack = (e) => {
        const audio = new Audio();
        audio.srcObject = e.streams[0];
        audio.play().catch(() => {});
      };

      pc.oniceconnectionstatechange = () => {
        const state = pc.iceConnectionState;
        if (state === 'connected' || state === 'completed') setStatus('connected');
        else if (state === 'failed' || state === 'closed') setStatus('disconnected');
      };

      pc.onicecandidate = async (e) => {
        if (!e.candidate) return;
        const c = {
          candidate: e.candidate.candidate,
          sdp_mid: e.candidate.sdpMid,
          sdp_mline_index: e.candidate.sdpMLineIndex,
        };
        if (canSend) {
          await invoke('ice_candidate', { pc_id: pc._pcId, candidates: [c] }).catch(() => {});
        } else {
          pendingCandidates.push(c);
        }
      };

      // 4. Capture mic
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      pc.addTransceiver(stream.getAudioTracks()[0], { direction: 'sendrecv' });

      // 5. Create and send offer
      const offer = await pc.createOffer({ offerToReceiveAudio: 1 });
      await pc.setLocalDescription(offer);

      const answer = await invoke('offer', { sdp: offer.sdp, type: offer.type });
      pc._pcId = answer.pc_id;
      await pc.setRemoteDescription(new RTCSessionDescription({ sdp: answer.sdp, type: answer.type }));

      // 6. Flush queued candidates
      canSend = true;
      for (const c of pendingCandidates) {
        await invoke('ice_candidate', { pc_id: pc._pcId, candidates: [c] }).catch(() => {});
      }

      // 7. Wait for ICE to actually connect (proves end-to-end works)
      await new Promise((resolve, reject) => {
        if (pc.iceConnectionState === 'connected' || pc.iceConnectionState === 'completed') {
          return resolve();
        }
        const origHandler = pc.oniceconnectionstatechange;
        const timeout = setTimeout(() => reject(new Error('ICE timeout')), 10000);
        pc.oniceconnectionstatechange = () => {
          const state = pc.iceConnectionState;
          if (state === 'connected' || state === 'completed') {
            clearTimeout(timeout);
            pc.oniceconnectionstatechange = origHandler;
            origHandler?.();
            resolve();
          } else if (state === 'failed' || state === 'closed') {
            clearTimeout(timeout);
            reject(new Error('ICE failed'));
          }
          origHandler?.();
        };
      });

      setStatus('connected');
    } catch (err) {
      console.error('[WebRTC] Connection failed:', err);
      // Remove a server-side peer before changing the AgentCore runtime session.
      const failedPeer = pcRef.current;
      const failedPcId = failedPeer?._pcId;
      if (failedPeer) {
        failedPeer.getSenders().forEach((s) => s.track?.stop());
        failedPeer.close();
        pcRef.current = null;
      }
      if (failedPcId) {
        try {
          await invoke('disconnect', { pc_id: failedPcId });
        } catch (cleanupError) {
          console.warn('[WebRTC] Failed to clean up server peer:', cleanupError);
        }
      }
      sessionIdRef.current = null;
      setStatus('disconnected');
      throw err;
    }
  }, [invoke]);

  // Retry transient signaling/ICE failures once with a fresh AgentCore runtime session.
  const connectWithRetry = useCallback(async () => {
    try {
      await connect();
    } catch (err) {
      if (['NotAllowedError', 'NotFoundError', 'SecurityError'].includes(err?.name)) {
        throw err;
      }
      console.warn('[WebRTC] First attempt failed, retrying...', err.message);
      try {
        await connect();
      } catch (retryError) {
        console.error('[WebRTC] Retry also failed:', retryError.message);
        setStatus('disconnected');
        throw retryError;
      }
    }
  }, [connect]);

  const disconnect = useCallback(async () => {
    if (pcRef.current) {
      const pcId = pcRef.current._pcId;
      pcRef.current.getSenders().forEach((s) => s.track?.stop());
      pcRef.current.close();
      pcRef.current = null;
      if (pcId) {
        try {
          await invoke('disconnect', { pc_id: pcId });
        } catch (err) {
          console.warn('[WebRTC] Failed to clean up server peer:', err);
        }
      }
    }
    sessionIdRef.current = null;
    setStatus('disconnected');
  }, [invoke]);

  useEffect(() => {
    return () => {
      if (pcRef.current) {
        pcRef.current.getSenders().forEach((s) => s.track?.stop());
        pcRef.current.close();
      }
    };
  }, []);

  return { status, transcripts, connect: connectWithRetry, disconnect };
}
