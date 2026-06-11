import { useRef, useMemo, useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Briefcase, Hexagon, ShieldCheck, ArrowRight, Terminal } from 'lucide-react';
import { motion, useScroll, useTransform, MotionValue } from 'framer-motion';

// --- DOM SCENE COMPONENTS (Framer Motion) --- //

function FallingResume({ 
    scrollYProgress, 
    config
}: { 
    scrollYProgress: MotionValue<number>; 
    config: any;
}) {
    const y = useTransform(scrollYProgress, [0, 0.5], [config.yStart, config.yEnd * config.speed]);
    const rotate = useTransform(scrollYProgress, [0, 0.5], [config.rotationStart, config.rotationStart + 180 * config.speed]);
    
    return (
        <motion.img
            src={`/images/resume${config.textureIdx}.png`}
            alt="Resume"
            className="absolute rounded shadow-[0_15px_35px_rgba(0,0,0,0.12)] object-contain origin-center opacity-30 border border-slate-100 bg-white"
            style={{ 
                top: '50%', 
                left: '50%',
                x: config.x,
                y,
                rotate,
                scale: config.scale,
                width: '18vw',
                minWidth: '200px',
                pointerEvents: 'none',
                filter: 'drop-shadow(0 8px 16px rgba(0,0,0,0.06))'
            }}
        />
    );
}

function FinalVerifiedResume({ scrollYProgress, viewportHeight }: { scrollYProgress: MotionValue<number>, viewportHeight: number }) {
    const y = useTransform(scrollYProgress, [0.4, 0.65], [viewportHeight, 0]);
    const rotate = useTransform(scrollYProgress, [0.4, 0.65], [20, 0]);
    
    return (
        <motion.img
            src="/images/resume1.png"
            alt="Final Resume"
            className="absolute shadow-[0_30px_70px_rgba(0,0,0,0.15)] rounded object-contain border border-slate-200 bg-white"
            style={{
                top: '50%',
                left: '50%',
                x: '-50%',
                marginTop: '-30vh',
                y,
                rotate,
                width: '35vw',
                minWidth: '350px',
                pointerEvents: 'none',
                zIndex: 10
            }}
        />
    );
}

function VerifiedStamp({ scrollYProgress }: { scrollYProgress: MotionValue<number> }) {
    const scale = useTransform(scrollYProgress, [0.75, 0.82], [10, 1.0]);
    const opacity = useTransform(scrollYProgress, [0.75, 0.78, 0.82], [0, 1, 1]);
    const rotate = useTransform(scrollYProgress, [0.75, 0.82], [-30, -12]);

    return (
        <motion.img
            src="/images/verified_flat.png"
            alt="Verified Ink Stamp"
            className="absolute opacity-90"
            style={{
                top: '50%',
                left: '50%',
                x: '-50%',
                marginTop: '-22vh',
                rotate,
                scale,
                opacity,
                width: '16vw',
                minWidth: '180px',
                maxWidth: '260px',
                pointerEvents: 'none',
                zIndex: 20,
                mixBlendMode: 'multiply',
                filter: 'contrast(1.2) brightness(1.05)', // preserve vibrant red color and push off-white pixels to pure white for perfect transparency
                objectFit: 'contain',
            }}
        />
    );
}

// --- MAIN WRAPPER --- //

export default function Landing() {
    const { scrollYProgress } = useScroll();
    
    const [viewport, setViewport] = useState({ width: 1000, height: 800 });
    
    useEffect(() => {
        setViewport({ width: window.innerWidth, height: window.innerHeight });
        const onResize = () => setViewport({ width: window.innerWidth, height: window.innerHeight });
        window.addEventListener('resize', onResize);
        return () => window.removeEventListener('resize', onResize);
    }, []);

    const resumesConfig = useMemo(() => {
        return Array.from({ length: 30 }).map(() => ({
            x: (Math.random() - 0.5) * viewport.width * 1.5 - 150,
            yStart: -viewport.height - Math.random() * viewport.height,
            yEnd: viewport.height + Math.random() * viewport.height,
            scale: Math.random() * 0.5 + 0.6,
            rotationStart: Math.random() * 360,
            textureIdx: Math.random() > 0.5 ? 1 : 2,
            speed: Math.random() * 1.5 + 0.5
        }));
    }, [viewport.width, viewport.height]);

    const opPage1 = useTransform(scrollYProgress, [0, 0.1, 0.2, 1], [1, 1, 0, 0]);
    const opPage2 = useTransform(scrollYProgress, [0, 0.2, 0.3, 0.45, 0.55, 1], [0, 0, 1, 1, 0, 0]);
    const opPage3 = useTransform(scrollYProgress, [0, 0.55, 0.65, 0.75, 0.85, 1], [0, 0, 1, 1, 0, 0]);
    const opPage4 = useTransform(scrollYProgress, [0, 0.85, 0.95, 1], [0, 0, 1, 1]);

    return (
        <div className="relative w-full h-[400vh] bg-slate-50 font-body text-slate-800">
            <div className="sticky top-0 w-full h-screen overflow-hidden flex flex-col justify-center items-center">
                
                {/* GLOBAL NAV */}
                <nav className="absolute top-0 w-full flex justify-between items-center px-10 py-6 z-50 bg-white/80 backdrop-blur-xl border-b border-slate-200/80 shadow-sm">
                    <div className="flex items-center space-x-3 group">
                        <div className="text-slate-900 p-1.5 border border-slate-200 rounded shadow-[0_4px_10px_rgba(0,0,0,0.05)] bg-slate-50 transition-colors group-hover:bg-slate-100">
                            <Hexagon className="w-6 h-6" />
                        </div>
                        <span className="text-3xl font-editorial tracking-wide text-slate-900">
                            SkillBridge
                        </span>
                    </div>
                    <div className="flex space-x-6 items-center">
                        <Link to="/login" className="text-sm font-terminal uppercase tracking-[0.2em] text-slate-600 hover:text-slate-900 transition-colors flex items-center space-x-2">
                            <Terminal className="w-4 h-4" />
                            <span>Login</span>
                        </Link>
                        <div className="group relative">
                            <button className="px-6 py-3 bg-slate-900 text-white font-editorial font-bold text-lg rounded hover:bg-slate-855 transition-colors shadow-[0_4px_12px_rgba(0,0,0,0.1)] flex items-center space-x-2">
                                <span>Sign Up</span>
                                <ArrowRight className="w-4 h-4" />
                            </button>
                            <div className="absolute right-0 mt-3 w-56 bg-white rounded-xl shadow-2xl border border-slate-200 opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-200">
                                <Link to="/register/candidate" className="block px-6 py-4 text-[11px] font-terminal uppercase tracking-widest text-slate-800 hover:bg-slate-50 hover:text-slate-905 border-b border-slate-100 transition rounded-t-xl">
                                    Candidate Sign Up
                                </Link>
                                <Link to="/register/recruiter" className="block px-6 py-4 text-[11px] font-terminal uppercase tracking-widest text-emerald-700 hover:bg-slate-50 hover:text-emerald-800 transition rounded-b-xl">
                                    Recruiter Sign Up
                                </Link>
                            </div>
                        </div>
                    </div>
                </nav>

                {/* 3D SCROLLYTELLING ELEMENTS */}
                <div className="absolute inset-0 z-0 pointer-events-none perspective-[1000px] bg-[radial-gradient(circle_at_center,rgba(0,0,0,0.01)_0%,transparent_60%)]">
                    {resumesConfig.map((config, i) => (
                        <FallingResume key={i} scrollYProgress={scrollYProgress} config={config} />
                    ))}
                    <FinalVerifiedResume scrollYProgress={scrollYProgress} viewportHeight={viewport.height} />
                    <VerifiedStamp scrollYProgress={scrollYProgress} />
                </div>

                {/* HTML TEXT OVERLAYS */}
                <motion.div 
                    style={{ opacity: opPage1 }} 
                    className="absolute w-full h-screen flex flex-col justify-center items-center text-center px-6 z-30 pointer-events-none"
                >
                    <div className="bg-white/95 p-12 border border-slate-200 shadow-[0_30px_70px_rgba(0,0,0,0.06)] rounded-2xl relative overflow-hidden backdrop-blur-md max-w-3xl">
                        <div className="absolute top-0 left-0 w-2 h-full bg-slate-900"></div>
                        <h1 className="text-5xl md:text-7xl font-editorial leading-tight tracking-wide text-slate-900 mb-6">
                            Stop Relying on <br/>
                            <span className="text-slate-700 font-medium italic">Unverified Paper.</span>
                        </h1>
                        <p className="text-lg text-slate-500 font-terminal tracking-wider max-w-2xl mx-auto uppercase">
                            The legacy recruitment model is compromised.<br/> 
                            Scroll to initialize the SkillBridge Verification Ledger.
                        </p>
                    </div>
                </motion.div>

                <motion.div 
                    style={{ opacity: opPage2 }} 
                    className="absolute w-full h-screen flex flex-col justify-center items-start px-12 lg:px-32 text-left z-30 pointer-events-none"
                >
                    <div className="bg-white/95 p-10 rounded-2xl border border-slate-200 shadow-[0_30px_70px_rgba(0,0,0,0.06)] relative overflow-hidden backdrop-blur-md">
                        <div className="absolute top-0 left-0 w-full h-1 bg-slate-900"></div>
                        <h2 className="text-2xl font-terminal uppercase tracking-[0.2em] text-slate-900 mb-4 font-semibold">
                            System Active // Agentic Parsing
                        </h2>
                        <p className="text-xl font-editorial text-slate-700 max-w-md leading-relaxed">
                            Our LangGraph nodes automatically ingest resumes, discarding fluff and constructing a strict, verified telemetry profile.
                        </p>
                    </div>
                </motion.div>

                <motion.div 
                    style={{ opacity: opPage3 }} 
                    className="absolute w-full h-screen flex flex-col justify-center items-end px-12 lg:px-32 text-right z-30 pointer-events-none"
                >
                    <div className="bg-white/95 p-10 rounded-2xl border border-slate-200 shadow-[0_30px_70px_rgba(0,0,0,0.06)] relative overflow-hidden backdrop-blur-md">
                        <div className="absolute top-0 right-0 w-1 h-full bg-emerald-600"></div>
                        <h2 className="text-2xl font-terminal uppercase tracking-[0.2em] text-emerald-700 mb-4 font-semibold">
                            Co-Pilot // Sandbox Validation
                        </h2>
                        <p className="text-xl font-editorial text-slate-700 max-w-md ml-auto leading-relaxed">
                            WebRTC-enabled algorithmic evaluators conduct live audio coding tests. Only candidates passing standard deviation checks reach your desk.
                        </p>
                    </div>
                </motion.div>

                <motion.div 
                    style={{ opacity: opPage4 }} 
                    className="absolute w-full h-screen flex flex-col justify-end pb-40 items-center text-center z-40"
                >
                    <div className="bg-white/95 p-12 rounded-2xl border border-slate-200 shadow-[0_30px_70px_rgba(0,0,0,0.06)] max-w-4xl w-full mx-auto relative overflow-hidden backdrop-blur-md">
                        <ShieldCheck className="w-16 h-16 text-slate-900 mx-auto mb-8 opacity-90" />
                        <h1 className="text-4xl md:text-6xl font-editorial text-slate-900 mb-8 tracking-wide font-medium">
                            Hire with <span className="italic text-slate-700">Absolute Certainty.</span>
                        </h1>
                        
                        <div className="flex flex-col sm:flex-row justify-center items-center gap-6 mt-12 pointer-events-auto">
                            <Link to="/register/candidate" className="w-full sm:w-auto px-8 py-5 bg-transparent border border-slate-350 text-slate-700 font-terminal text-[13px] uppercase tracking-[0.2em] rounded hover:bg-slate-50 transition shadow-[0_0_15px_rgba(0,0,0,0.02)]">
                                Sign Up as Candidate
                            </Link>
                            <Link to="/register/recruiter" className="w-full sm:w-auto px-8 py-5 bg-slate-900 text-white font-editorial font-bold text-lg rounded hover:bg-slate-800 transition shadow-[0_10px_25px_rgba(0,0,0,0.15)] flex items-center justify-center space-x-3">
                                <span>Sign Up as Recruiter</span>
                                <Briefcase className="w-5 h-5" />
                            </Link>
                        </div>
                    </div>
                </motion.div>

            </div>
        </div>
    );
}
