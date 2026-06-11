import { useState, useEffect, useRef } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { Mic, BrainCircuit, Activity, StopCircle, Maximize2, Terminal, Loader2, Play } from 'lucide-react';
import Editor from '@monaco-editor/react';
import { getWebSocketURL } from '../../services/api';

export default function BotInterview() {
    const [searchParams] = useSearchParams();
    // Use session_id (interview session ID) as the WS room key - NOT app_id
    const sessionId = searchParams.get('session_id') || searchParams.get('app_id') || 'demo-session';
    const navigate = useNavigate();

    const [loading, setLoading] = useState(true);
    const [interviewActive, setInterviewActive] = useState(false);
    const [isWaiting, setIsWaiting] = useState(false);
    const [isListening, setIsListening] = useState(false);
    const [isSpeaking, setIsSpeaking] = useState(false);
    
    // UI state
    const [transcript, setTranscript] = useState<{ role: string, text: string }[]>([]);
    const [code, setCode] = useState('// Write your javascript solution here\nfunction solve() {\n  console.log("Hello, World!");\n}\nsolve();');
    const [output, setOutput] = useState<string>('');
    const [isRunning, setIsRunning] = useState(false);
    
    // Refs
    const wsRef = useRef<WebSocket | null>(null);
    const recognitionRef = useRef<any>(null);
    const synthesisRef = useRef<SpeechSynthesis | null>(null);
    
    // WebRTC Refs
    const localVideoRef = useRef<HTMLVideoElement>(null);
    const remoteVideoRef = useRef<HTMLVideoElement>(null);
    const peerConnectionRef = useRef<RTCPeerConnection | null>(null);
    const webRTCInitialized = useRef(false);

    const initWebRTC = async (ws: WebSocket) => {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
            if (localVideoRef.current) localVideoRef.current.srcObject = stream;
            
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
            
            // Notify recruiter we are ready for the offer
            ws.send(JSON.stringify({ type: 'candidate_webrtc_ready' }));
        } catch (err) {
            console.error("WebRTC Error:", err);
        }
    };

    useEffect(() => {
        if (interviewActive && !isWaiting && wsRef.current && !webRTCInitialized.current) {
            webRTCInitialized.current = true;
            initWebRTC(wsRef.current);
        }
    }, [interviewActive, isWaiting]);

    useEffect(() => {
        if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
            const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
            recognitionRef.current = new SpeechRecognition();
            recognitionRef.current.continuous = false;
            recognitionRef.current.interimResults = false;

            recognitionRef.current.onresult = (event: any) => {
                const text = event.results[0][0].transcript;
                if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
                    wsRef.current.send(JSON.stringify({ type: 'candidate_speech', text }));
                }
            };
            recognitionRef.current.onend = () => {
                setIsListening(false);
            };
        }
        if ('speechSynthesis' in window) {
            synthesisRef.current = window.speechSynthesis;
        }
        setLoading(false);
    }, []);

    const startInterview = () => {
        setLoading(true);
        const ws = new WebSocket(getWebSocketURL(`/ws/live-interview/${sessionId}/candidate`));
        
        ws.onopen = () => {
            setInterviewActive(true);
            setLoading(false);
        };
        
        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            
            if (data.type === 'waiting_room') {
                setIsWaiting(true);
            } else if (data.type === 'recruiter_joined') {
                setIsWaiting(false);
            } else if (data.type === 'candidate_speech') {
                setTranscript(prev => [...prev, { role: 'candidate', text: data.text }]);
            } else if (data.type === 'recruiter_speech') {
                setTranscript(prev => [...prev, { role: 'recruiter', text: data.text }]);
            } else if (data.type === 'bot_speaks') {
                setTranscript(prev => [...prev, { role: 'bot', text: data.text }]);
                speak(data.text);
            } else if (data.type === 'code_update' && data.sender !== 'candidate') {
                setCode(data.code);
            } else if (data.type === 'output_update' && data.sender !== 'candidate') {
                setOutput(data.output);
            } else if (data.type === 'offer') {
                // We got the offer from the recruiter
                const pc = peerConnectionRef.current;
                if (pc) {
                    pc.setRemoteDescription(new RTCSessionDescription(data.offer))
                    .then(() => pc.createAnswer())
                    .then(answer => pc.setLocalDescription(answer).then(() => {
                        ws.send(JSON.stringify({ type: 'answer', answer }));
                    }))
                    .catch(console.error);
                }
            } else if (data.type === 'ice_candidate') {
                if (peerConnectionRef.current) {
                    peerConnectionRef.current.addIceCandidate(new RTCIceCandidate(data.candidate)).catch(console.error);
                }
            }
        };
        
        ws.onclose = () => {
            setInterviewActive(false);
            alert("Interview Session Ended");
            navigate('/dashboard/candidate/applications');
        };

        wsRef.current = ws;
    };

    const handleCodeChange = (newCode: string) => {
        setCode(newCode);
        if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
            wsRef.current.send(JSON.stringify({ type: 'code_update', code: newCode }));
        }
    };

    const runCode = async () => {
        setIsRunning(true);
        setOutput('Running...');
        try {
            const response = await fetch('https://emkc.org/api/v2/piston/execute', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    language: 'javascript',
                    version: '18.15.0',
                    files: [{ content: code }]
                })
            });
            const data = await response.json();
            const result = data.run.output || 'No output generated';
            setOutput(result);
            if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
                wsRef.current.send(JSON.stringify({ type: 'output_update', output: result }));
            }
        } catch (error: any) {
            setOutput('Error executing code: ' + error.message);
            if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
                wsRef.current.send(JSON.stringify({ type: 'output_update', output: 'Error executing code' }));
            }
        } finally {
            setIsRunning(false);
        }
    };

    const toggleMic = () => {
        if (!recognitionRef.current) return alert("Speech Recognition not supported in this browser.");
        
        if (isListening) {
            recognitionRef.current.stop();
        } else {
            setIsListening(true);
            recognitionRef.current.start();
        }
    };

    const speak = (text: string) => {
        if (!synthesisRef.current) return;
        setIsSpeaking(true);
        synthesisRef.current.cancel();

        const utterance = new SpeechSynthesisUtterance(text);
        utterance.rate = 0.95;
        utterance.onend = () => setIsSpeaking(false);
        
        const voices = synthesisRef.current.getVoices();
        const preferredVoice = voices.find(v => v.name.includes('Google') || v.name.includes('Samantha'));
        if (preferredVoice) utterance.voice = preferredVoice;

        synthesisRef.current.speak(utterance);
    };

    const endInterview = () => {
        if (synthesisRef.current) synthesisRef.current.cancel();
        if (recognitionRef.current) recognitionRef.current.stop();
        if (wsRef.current) wsRef.current.close();
    };

    if (loading) return <div className="p-8"><Activity className="w-8 h-8 animate-spin text-indigo-600 mx-auto" /></div>;

    return (
        <div className="max-w-6xl mx-auto h-[calc(100vh-6rem)] flex flex-col pt-4">
            {!interviewActive ? (
                <div className="flex-1 flex flex-col items-center justify-center bg-white rounded-3xl border border-gray-100 shadow-xl p-12 text-center">
                    <div className="w-24 h-24 bg-indigo-50 rounded-full flex items-center justify-center mb-8 relative">
                        <div className="absolute inset-0 bg-indigo-500 rounded-full animate-ping opacity-20"></div>
                        <BrainCircuit className="w-12 h-12 text-indigo-600" />
                    </div>
                    <h1 className="text-4xl font-black text-gray-900 mb-4 tracking-tight">Live Co-Pilot Interview</h1>
                    <p className="text-xl text-gray-600 mb-8 max-w-lg mx-auto">
                        In this session, you'll be speaking with your hiring manager assisted by our autonomous AI agent. It includes a live code environment.
                    </p>
                    <button
                        onClick={startInterview}
                        className="px-10 py-5 bg-indigo-600 hover:bg-indigo-700 text-white font-black text-lg rounded-2xl shadow-xl shadow-indigo-200 transition-transform transform hover:-translate-y-1 flex items-center space-x-3"
                    >
                        <Mic className="w-6 h-6" />
                        <span>Join Live Session</span>
                    </button>
                </div>
            ) : isWaiting ? (
                <div className="flex-1 flex flex-col items-center justify-center bg-white rounded-3xl border border-gray-100 shadow-xl p-12 text-center">
                    <div className="relative w-24 h-24 bg-indigo-50 rounded-full flex items-center justify-center mb-8">
                        <div className="absolute inset-0 bg-indigo-500 rounded-full animate-ping opacity-20"></div>
                        <Loader2 className="w-10 h-10 text-indigo-600 animate-spin" />
                    </div>
                    <h1 className="text-4xl font-black text-gray-900 mb-4 tracking-tight">Waiting Room...</h1>
                    <p className="text-xl text-gray-600 mb-8 max-w-lg mx-auto">
                        Please hold on. Your recruiter has been notified and will let you into the live session shortly.
                    </p>
                    <button onClick={endInterview} className="px-6 py-3 bg-gray-100 hover:bg-gray-200 text-gray-700 font-bold rounded-xl transition">
                        Leave Waiting Room
                    </button>
                </div>
            ) : (
                <div className="flex-1 grid grid-cols-1 lg:grid-cols-2 gap-6 pb-6">
                    {/* AV / Chat Feed */}
                    <div className="bg-slate-900 rounded-3xl shadow-xl overflow-hidden border border-slate-800 flex flex-col relative">
                        <div className="bg-slate-800 p-4 border-b border-slate-700 shadow-sm flex justify-between items-center z-10">
                            <div className="flex items-center space-x-3">
                                <div className={`w-3 h-3 rounded-full ${isSpeaking ? 'bg-indigo-500 animate-pulse' : 'bg-green-500'}`}></div>
                                <span className="text-white font-bold text-sm tracking-wide uppercase">AI & Interviewer Feed</span>
                            </div>
                            <button onClick={endInterview} className="bg-red-500 hover:bg-red-600 text-white px-3 py-1.5 rounded-lg text-sm font-bold transition">
                                Leave Room
                            </button>
                        </div>
                        
                        <div className="bg-black border-b border-slate-700 h-64 relative overflow-hidden flex items-center justify-center relative shadow-inner">
                            <video ref={remoteVideoRef} autoPlay playsInline className="absolute inset-0 w-full h-full object-cover opacity-90" />
                            <div className="absolute top-4 left-4 bg-black/50 text-white text-xs px-2 py-1 rounded backdrop-blur-md">Recruiter Cam</div>
                            
                            <div className="absolute bottom-4 right-4 w-32 h-24 bg-black/80 rounded-xl overflow-hidden shadow-2xl border border-slate-700">
                                <video ref={localVideoRef} autoPlay playsInline muted className="w-full h-full object-cover -scale-x-100" />
                            </div>
                        </div>

                        <div className="flex-1 p-6 overflow-y-auto space-y-4">
                            {transcript.map((msg, idx) => (
                                <div key={idx} className={`p-4 rounded-xl max-w-[85%] ${msg.role === 'candidate' ? 'bg-indigo-600 text-white ml-auto' : msg.role === 'bot' ? 'bg-white text-gray-900 border border-gray-200' : 'bg-slate-700 text-slate-100 border border-slate-600'}`}>
                                    <div className={`text-xs font-bold uppercase mb-1 ${msg.role === 'candidate' ? 'text-indigo-200' : msg.role === 'bot' ? 'text-indigo-600' : 'text-slate-400'}`}>
                                        {msg.role === 'candidate' ? 'You' : msg.role === 'bot' ? 'AI Assistant' : 'Interviewer'}
                                    </div>
                                    <p className="leading-relaxed">{msg.text}</p>
                                </div>
                            ))}
                        </div>
                        
                        <div className="p-6 bg-slate-950 border-t border-slate-800 flex justify-center items-center">
                            <button
                                onClick={toggleMic}
                                className={`w-16 h-16 rounded-full flex items-center justify-center transition-all ${isListening
                                    ? 'bg-red-500 text-white shadow-lg shadow-red-500/30 animate-pulse'
                                    : 'bg-indigo-600 hover:bg-indigo-500 text-white shadow-lg'
                                    }`}
                            >
                                {isListening ? <StopCircle className="w-6 h-6" /> : <Mic className="w-6 h-6" />}
                            </button>
                            <div className="ml-4 text-slate-400 text-sm font-medium">
                                {isListening ? "Listening... click to send" : "Click mic to speak"}
                            </div>
                        </div>
                    </div>

                    {/* Integrated Code Editor */}
                    <div className="bg-[#1e1e1e] rounded-3xl shadow-xl overflow-hidden border border-slate-800 flex flex-col">
                        <div className="bg-[#2d2d2d] py-3 px-4 flex items-center justify-between border-b mx-0 border-black shadow">
                            <div className="flex items-center space-x-2 text-gray-300 font-medium text-sm">
                                <Terminal className="w-4 h-4" />
                                <span>Live Code Editor</span>
                            </div>
                            <div className="flex items-center space-x-3">
                                <button
                                    onClick={runCode}
                                    disabled={isRunning}
                                    className="flex items-center space-x-1 bg-green-600 hover:bg-green-500 text-white text-xs font-bold px-3 py-1.5 rounded disabled:opacity-50"
                                >
                                    {isRunning ? <Loader2 className="w-3 h-3 animate-spin"/> : <Play className="w-3 h-3"/>}
                                    <span>Run</span>
                                </button>
                                <Maximize2 className="w-4 h-4 text-gray-500 cursor-pointer hover:text-white" />
                            </div>
                        </div>
                        <div className="flex flex-col flex-1">
                            <div className="h-2/3 border-b border-black">
                                <Editor
                                    height="100%"
                                    defaultLanguage="javascript"
                                    theme="vs-dark"
                                    value={code}
                                    onChange={(value) => handleCodeChange(value || '')}
                                    options={{
                                        minimap: { enabled: false },
                                        fontSize: 14,
                                        wordWrap: "on",
                                        padding: { top: 16 }
                                    }}
                                />
                            </div>
                            <div className="h-1/3 bg-[#1e1e1e] p-4 overflow-y-auto">
                                <div className="text-gray-400 text-xs font-bold uppercase mb-2">Console Output</div>
                                <pre className="font-mono text-sm text-green-400 whitespace-pre-wrap">{output}</pre>
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
