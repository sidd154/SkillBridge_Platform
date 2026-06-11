import { useState, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { BrainCircuit, Loader2, Send, Terminal, PlayCircle, Check, X, TerminalSquare } from 'lucide-react';
import Editor from '@monaco-editor/react';
import api, { getWebSocketURL } from '../../services/api';

export default function LiveSession() {
    const { sessionId } = useParams();
    const navigate = useNavigate();

    const [loading, setLoading] = useState(false);
    const [interviewActive, setInterviewActive] = useState(false);
    
    // UI state
    const [transcript, setTranscript] = useState<{ role: string, text: string }[]>([]);
    const [code, setCode] = useState('// Waiting for candidate telemetry...\n');
    const [manualQuestion, setManualQuestion] = useState('');
    const [suggestedQuestion, setSuggestedQuestion] = useState<{ id: string, text: string } | null>(null);
    const [botLoading, setBotLoading] = useState(false);
    const [output, setOutput] = useState<string>('');
    
    // Refs
    const wsRef = useRef<WebSocket | null>(null);
    const localVideoRef = useRef<HTMLVideoElement>(null);
    const remoteVideoRef = useRef<HTMLVideoElement>(null);
    const peerConnectionRef = useRef<RTCPeerConnection | null>(null);

    const initWebRTC = async (ws: WebSocket) => {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
            if (localVideoRef.current) {
                localVideoRef.current.srcObject = stream;
            }
            
            const pc = new RTCPeerConnection({ iceServers: [{ urls: 'stun:stun.l.google.com:19302' }] });
            peerConnectionRef.current = pc;
            
            stream.getTracks().forEach(track => pc.addTrack(track, stream));
            
            pc.onicecandidate = (event) => {
                if (event.candidate && ws.readyState === WebSocket.OPEN) {
                    ws.send(JSON.stringify({ type: 'ice_candidate', candidate: event.candidate }));
                }
            };
            
            pc.ontrack = (event) => {
                if (remoteVideoRef.current && event.streams[0]) {
                    remoteVideoRef.current.srcObject = event.streams[0];
                }
            };
            
            // Create offer immediately
            const offer = await pc.createOffer();
            await pc.setLocalDescription(offer);
            ws.send(JSON.stringify({ type: 'offer', offer }));
        } catch (err) {
            console.error("WebRTC Error:", err);
        }
    };

    const startSession = () => {
        setLoading(true);
        const ws = new WebSocket(getWebSocketURL(`/ws/live-interview/${sessionId || 'demo'}/recruiter`));
        
        ws.onopen = () => {
            setInterviewActive(true);
            setLoading(false);
            initWebRTC(ws);
        };
        
        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            
            if (data.type === 'bot_speaks') {
                setTranscript(prev => [...prev, { role: 'bot', text: data.text }]);
            } else if (data.type === 'candidate_speech') {
                setTranscript(prev => [...prev, { role: 'candidate', text: data.text }]);
            } else if (data.type === 'bot_suggestion') {
                setSuggestedQuestion({ id: Date.now().toString(), text: data.text });
                setBotLoading(false);
            } else if (data.type === 'code_update') {
                setCode(data.code);
            } else if (data.type === 'output_update') {
                setOutput(data.output);
            } else if (data.type === 'candidate_webrtc_ready') {
                if (peerConnectionRef.current && wsRef.current) {
                    peerConnectionRef.current.createOffer()
                    .then(offer => peerConnectionRef.current!.setLocalDescription(offer).then(() => {
                        wsRef.current!.send(JSON.stringify({ type: 'offer', offer }));
                    })).catch(console.error);
                }
            } else if (data.type === 'answer') {
                if (peerConnectionRef.current) {
                    peerConnectionRef.current.setRemoteDescription(new RTCSessionDescription(data.answer));
                }
            } else if (data.type === 'ice_candidate') {
                if (peerConnectionRef.current) {
                    peerConnectionRef.current.addIceCandidate(new RTCIceCandidate(data.candidate));
                }
            }
        };
        
        ws.onclose = () => {
            setInterviewActive(false);
            navigate('/dashboard/recruiter/jobs');
        };

        wsRef.current = ws;
    };

    const requestBotSuggestion = () => {
        if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
        setBotLoading(true);
        wsRef.current.send(JSON.stringify({ type: 'request_bot_suggestion' }));
    };

    const approveQuestion = () => {
        if (!wsRef.current || !suggestedQuestion) return;
        wsRef.current.send(JSON.stringify({ type: 'approve_bot_question', text: suggestedQuestion.text }));
        setSuggestedQuestion(null);
    };

    const rejectQuestion = () => {
        setSuggestedQuestion(null);
    };

    const sendManualQuestion = (e: React.FormEvent) => {
        e.preventDefault();
        if (!manualQuestion.trim() || !wsRef.current) return;
        
        wsRef.current.send(JSON.stringify({ type: 'recruiter_speech', text: manualQuestion }));
        setManualQuestion('');
    };

    const endSession = async () => {
        try {
            await api.post(`/interviews/${sessionId}/end`, {
                transcript,
                code_snapshot: code
            });
        } catch (e) {
            console.error(e);
        }
        if (wsRef.current) wsRef.current.close();
        navigate(`/dashboard/recruiter/interviews/summary/${sessionId}`);
    };

    if (loading) return <div className="p-8 flex justify-center"><Loader2 className="w-8 h-8 animate-spin text-fintech-amber mx-auto" /></div>;

    return (
        <div className="max-w-7xl mx-auto h-[calc(100vh-6rem)] flex flex-col font-body pb-6">
            {!interviewActive ? (
                <div className="flex-1 flex flex-col items-center justify-center bg-fintech-surface rounded-xl border border-fintech-border shadow-[0_20px_40px_rgba(0,0,0,0.5)] p-12 text-center relative overflow-hidden">
                    <div className="absolute top-0 right-0 w-full h-1 bg-[#63A583]"></div>
                    <div className="w-32 h-32 bg-[#1C202E] rounded-full flex items-center justify-center mb-8 border border-fintech-border shadow-[inset_0_0_20px_rgba(0,0,0,0.5)]">
                        <TerminalSquare className="w-12 h-12 text-[#63A583] opacity-80" />
                    </div>
                    <h1 className="text-4xl font-editorial font-medium text-fintech-cream mb-4 tracking-wide">Recruiter Copilot Socket</h1>
                    <p className="text-[11px] font-terminal uppercase tracking-widest text-fintech-ash mb-10 max-w-lg mx-auto leading-relaxed">
                        Awaiting your authorization to bind the connection. The candidate node is active and ready to stream telemetry.
                    </p>
                    <button
                        onClick={startSession}
                        className="px-10 py-5 bg-[#63A583] hover:bg-[#78C49F] text-fintech-base font-editorial font-bold text-lg rounded shadow-[0_0_20px_rgba(99,165,131,0.3)] hover:shadow-[0_0_25px_rgba(99,165,131,0.5)] transition-all flex items-center space-x-3"
                    >
                        <span>Initiate Socket Handshake</span>
                    </button>
                </div>
            ) : (
                <div className="flex-1 flex gap-6">
                    {/* Transcript & Copilot Panel */}
                    <div className="w-1/2 flex flex-col gap-6">
                        
                        {/* Video Panel & Feed */}
                        <div className="flex-1 bg-fintech-surface rounded-xl shadow-[0_10px_30px_rgba(0,0,0,0.5)] border border-fintech-border flex flex-col overflow-hidden relative">
                            <div className="bg-[#1C202E] border-b border-fintech-border px-6 py-4 flex justify-between items-center z-10">
                                <div className="text-[10px] font-terminal uppercase tracking-[0.2em] text-[#63A583] flex items-center">
                                    <span className="w-2 h-2 rounded-full bg-[#63A583] animate-pulse mr-2 shadow-[0_0_8px_rgba(99,165,131,0.8)]"></span>
                                    WebRTC Encrypted Feed
                                </div>
                                <button onClick={endSession} className="text-red-400 text-[9px] uppercase font-terminal tracking-widest bg-red-500/10 border border-red-500/20 px-3 py-1.5 rounded hover:bg-red-500/20 transition-colors">Terminate</button>
                            </div>
                            
                            <div className="bg-fintech-base border-b border-fintech-border h-64 relative overflow-hidden flex items-center justify-center shadow-inner">
                                <video ref={remoteVideoRef} autoPlay playsInline className="absolute inset-0 w-full h-full object-cover opacity-80 grayscale-[0.2]" />
                                <div className="absolute top-4 left-4 bg-fintech-base/80 border border-fintech-border text-fintech-cream font-terminal text-[9px] uppercase tracking-widest px-2.5 py-1.5 rounded backdrop-blur-md">Incoming Node</div>
                                
                                <div className="absolute bottom-4 right-4 w-32 h-24 bg-fintech-base rounded-xl overflow-hidden shadow-2xl border border-fintech-border">
                                    <video ref={localVideoRef} autoPlay playsInline muted className="w-full h-full object-cover -scale-x-100 opacity-90" />
                                </div>
                            </div>

                            <div className="flex-1 p-6 overflow-y-auto bg-[#181B26] space-y-5 custom-scrollbar">
                                {transcript.map((msg, idx) => (
                                    <div key={idx} className={`p-5 rounded max-w-[85%] border shadow-sm ${
                                        msg.role === 'recruiter' 
                                            ? 'bg-fintech-amber/10 border-fintech-amber/30 text-fintech-cream ml-auto' 
                                            : msg.role === 'bot' 
                                                ? 'bg-[#63A583]/10 border-[#63A583]/30 text-fintech-cream ml-auto' 
                                                : 'bg-fintech-surface border-fintech-border text-fintech-cream mr-auto'
                                    }`}>
                                        <div className={`text-[9px] font-terminal uppercase tracking-[0.2em] mb-2 opacity-70 ${
                                            msg.role === 'recruiter' ? 'text-fintech-amber' 
                                            : msg.role === 'bot' ? 'text-[#63A583]' 
                                            : 'text-fintech-ash'
                                        }`}>
                                            {msg.role === 'candidate' ? 'Entity Payload' : msg.role === 'bot' ? 'Agent Node' : 'Command Auth'}
                                        </div>
                                        <p className="leading-relaxed font-body text-[13px]">{msg.text}</p>
                                    </div>
                                ))}
                            </div>
                            
                            <form onSubmit={sendManualQuestion} className="p-5 bg-fintech-surface border-t border-fintech-border flex gap-4">
                                <input
                                    type="text"
                                    value={manualQuestion}
                                    onChange={e => setManualQuestion(e.target.value)}
                                    placeholder="Inject manual query payload..."
                                    className="flex-1 px-5 py-4 bg-fintech-base border border-fintech-border rounded focus:ring-1 focus:ring-fintech-amber focus:border-fintech-amber focus:outline-none font-terminal text-[12px] text-fintech-cream placeholder-fintech-ash/30 transition-all"
                                />
                                <button type="submit" disabled={!manualQuestion.trim()} className="px-6 py-4 bg-fintech-amber text-fintech-base disabled:bg-fintech-surface disabled:text-fintech-ash disabled:border-fintech-border font-editorial font-bold rounded shadow-[0_0_10px_rgba(232,168,48,0.2)] flex items-center justify-center transition-all">
                                    <Send className="w-4 h-4" />
                                </button>
                            </form>
                        </div>
                        
                        {/* Copilot Suggestions */}
                        <div className="h-48 bg-[#1C202E] rounded-xl border border-fintech-border p-6 flex flex-col shadow-[0_10px_30px_rgba(0,0,0,0.3)]">
                            <div className="flex justify-between items-center mb-4">
                                <h3 className="font-terminal text-[11px] uppercase tracking-[0.2em] text-[#63A583] flex items-center">
                                    <BrainCircuit className="w-4 h-4 mr-2" /> Agent Process // Copilot
                                </h3>
                                <button onClick={requestBotSuggestion} disabled={botLoading} className="text-[10px] font-terminal uppercase tracking-widest bg-[#63A583] hover:bg-[#78C49F] text-fintech-base px-4 py-2 font-bold rounded disabled:opacity-50 transition-colors shadow-[0_0_10px_rgba(99,165,131,0.2)]">
                                    {botLoading ? 'Computing...' : 'Generate Context'}
                                </button>
                            </div>
                            
                            <div className="flex-1 flex flex-col justify-center border-t border-fintech-border/50 pt-3">
                                {suggestedQuestion ? (
                                    <div className="bg-fintech-surface p-4 rounded border border-[#63A583]/30 flex justify-between items-center shadow-[inset_0_0_10px_rgba(99,165,131,0.05)]">
                                        <p className="text-fintech-cream text-[13px] font-body flex-1 mr-4">{suggestedQuestion.text}</p>
                                        <div className="flex gap-3">
                                            <button onClick={rejectQuestion} className="w-9 h-9 rounded bg-red-500/10 text-red-500 border border-red-500/20 flex items-center justify-center hover:bg-red-500/20 transition-colors">
                                                <X className="w-4 h-4" />
                                            </button>
                                            <button onClick={approveQuestion} className="px-4 h-9 rounded bg-[#63A583]/10 text-[#63A583] border border-[#63A583]/30 flex items-center justify-center hover:bg-[#63A583]/20 transition-colors text-[9px] font-terminal font-bold uppercase tracking-widest">
                                                <Check className="w-3.5 h-3.5 mr-1" /> Commit
                                            </button>
                                        </div>
                                    </div>
                                ) : (
                                    <p className="text-fintech-ash text-center text-[10px] font-terminal uppercase tracking-[0.2em] opacity-70">
                                        Awaiting agent generation prompt.
                                    </p>
                                )}
                            </div>
                        </div>

                    </div>

                    {/* Code Editor View */}
                    <div className="w-1/2 bg-fintech-base rounded-xl shadow-[0_10px_30px_rgba(0,0,0,0.5)] overflow-hidden border border-fintech-border flex flex-col">
                        <div className="bg-[#1C202E] py-4 px-6 flex items-center space-x-3 border-b border-fintech-border shadow">
                            <Terminal className="w-4 h-4 text-fintech-amber" />
                            <span className="text-fintech-ash font-terminal text-[10px] uppercase tracking-[0.2em]">Remote Telemetry // IDE Read-Only</span>
                        </div>
                        <div className="flex flex-col flex-1">
                            <div className="h-2/3 border-b border-fintech-border relative bg-fintech-base">
                                <Editor
                                    height="100%"
                                    defaultLanguage="javascript"
                                    theme="vs-dark"
                                    value={code}
                                    options={{
                                        readOnly: true,
                                        minimap: { enabled: false },
                                        fontSize: 14,
                                        wordWrap: "on",
                                        padding: { top: 16 }
                                    }}
                                />
                            </div>
                            <div className="h-1/3 bg-[#1C202E] p-6 overflow-y-auto">
                                <div className="text-[#63A583] text-[9px] font-terminal uppercase tracking-[0.2em] mb-4">Stdout / Stderr Protocol</div>
                                <pre className="font-terminal text-[12px] text-fintech-cream whitespace-pre-wrap opacity-80">{output || 'Waiting for remote execution loop...'}</pre>
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
