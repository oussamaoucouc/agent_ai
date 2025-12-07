import React, { useState, useEffect, useRef } from 'react';

interface AvatarProps {
    isSpeaking: boolean;
    isLoading: boolean;
    currentViseme: string;
    size?: 'large' | 'small';
}

// Redesigned, multi-part viseme shapes for a more realistic and expressive mouth.
// Refined shapes for smoother, more natural transitions
const visemeShapes: { [key: string]: { lips: string; inner?: string } } = {
    // A gentle, friendly, closed smile
    'sil': { lips: 'M 14 22 Q 20 25, 26 22 Q 20 24.5, 14 22 Z' },
    // Lips pressed together
    'PP': { lips: 'M 13 22.5 Q 20 23.5, 27 22.5 Q 20 23, 13 22.5 Z' },
    // Upper teeth touching a curved lower lip
    'FF': {
        lips: 'M 13 21.5 C 15 25, 25 25, 27 21.5 C 25 22.5, 15 22.5, 13 21.5 Z',
        inner: 'M 15 22 H 25 V 22.5 H 15 Z'
    },
    // Tongue peeking between lips
    'TH': {
        lips: 'M 14 21.5 C 16 25, 24 25, 26 21.5 Q 20 23, 14 21.5 Z',
        inner: 'M 17 22.5 Q 20 23.5, 23 22.5 Q 20 23, 17 22.5 Z'
    },
    // Mouth slightly open
    'DD': {
        lips: 'M 14 21 C 16 25, 24 25, 26 21 C 24 22, 16 22, 14 21 Z',
        inner: 'M 15 22.5 H 25 V 23 H 15 Z'
    },
    // Open mouth for 'k', 'g'
    'kk': {
        lips: 'M 15 20.5 C 17 25.5, 23 25.5, 25 20.5 C 23 22, 17 22, 15 20.5 Z',
        inner: 'M 17 23 Q 20 24.5, 23 23 Q 20 24, 17 23 Z'
    },
    // Pursed lips for 'ch', 'j'
    'CH': { lips: 'M 16 21.5 Q 20 25, 24 21.5 Q 20 24.5, 16 21.5 Z' },
    // Wide smile showing teeth
    'SS': {
        lips: 'M 12 22 C 15 25, 25 25, 28 22 C 25 23, 15 23, 12 22 Z',
        inner: 'M 14 22.5 H 26 V 23 H 14 Z'
    },
    // Open mouth, tongue raised
    'nn': {
        lips: 'M 14 20.5 C 17 25, 23 25, 26 20.5 C 23 22, 17 22, 14 20.5 Z',
        inner: 'M 16 22 Q 20 21, 24 22 L 23 23.5 L 17 23.5 Z'
    },
    // Rounded lips
    'RR': { lips: 'M 17 21.5 Q 20 24, 23 21.5 Q 20 23.5, 17 21.5 Z' },
    // 'ah' sound
    'aa': { lips: 'M 15 21 C 17 26, 23 26, 25 21 Q 20 25.5, 15 21 Z' },
    // 'eh' sound
    'E': { lips: 'M 13 21.5 C 17 25.5, 23 25.5, 27 21.5 C 23 22.5, 17 22.5, 13 21.5 Z' },
    // 'ih' sound
    'I': { lips: 'M 14 21.5 C 17 24.5, 23 24.5, 26 21.5 C 23 22.5, 17 22.5, 14 21.5 Z' },
    // 'oh' sound
    'O': { lips: 'M 16 21 Q 20 19, 24 21 Q 20 25, 16 21 Z' },
    // 'oo' sound
    'U': { lips: 'M 17 21.5 Q 20 19.5, 23 21.5 Q 20 24, 17 21.5 Z' },
};


export const Avatar: React.FC<AvatarProps> = ({ isSpeaking, isLoading, currentViseme, size = 'large' }) => {
    const avatarRef = useRef<HTMLDivElement>(null);
    const [pupilTransform, setPupilTransform] = useState({ x: 0, y: 0 });
    const [listeningShape, setListeningShape] = useState('sil');

    useEffect(() => {
        let animationTimeout: ReturnType<typeof setTimeout>;

        if (isSpeaking && currentViseme === 'X' && !isLoading) {
            const sequence = ['sil', 'PP', 'sil', 'I', 'sil', 'sil', 'CH', 'sil'];
            const animateMouth = () => {
                const nextShape = sequence[Math.floor(Math.random() * sequence.length)];
                setListeningShape(nextShape);
                const delay = (nextShape === 'sil' ? 2000 : 200) + Math.random() * 1000;
                animationTimeout = setTimeout(animateMouth, delay);
            };
            animationTimeout = setTimeout(animateMouth, 1500);
        } else {
            setListeningShape('sil');
        }

        return () => {
            clearTimeout(animationTimeout);
        };
    }, [isSpeaking, currentViseme, isLoading]);

    useEffect(() => {
        if (size !== 'large') return;

        const handleMouseMove = (event: MouseEvent) => {
            if (!avatarRef.current) return;

            const rect = avatarRef.current.getBoundingClientRect();
            const avatarCenterX = rect.left + rect.width / 2;
            const avatarCenterY = rect.top + rect.height / 2;

            const deltaX = event.clientX - avatarCenterX;
            const deltaY = event.clientY - avatarCenterY;

            const angle = Math.atan2(deltaY, deltaX);
            const distance = Math.sqrt(deltaX * deltaX + deltaY * deltaY);

            const MAX_DISTANCE = 300;
            const MAX_PUPIL_OFFSET = 1.5;
            const movementScale = Math.min(1, distance / MAX_DISTANCE);

            const pupilX = Math.cos(angle) * MAX_PUPIL_OFFSET * movementScale;
            const pupilY = Math.sin(angle) * MAX_PUPIL_OFFSET * movementScale;

            setPupilTransform({ x: pupilX, y: pupilY });
        };

        window.addEventListener('mousemove', handleMouseMove);
        return () => window.removeEventListener('mousemove', handleMouseMove);
    }, [size]);

    const apiVisemeToShapeKey: { [key: string]: string } = {
        'X': 'sil', 'A': 'aa', 'B': 'PP', 'C': 'SS', 'D': 'DD',
        'E': 'E', 'F': 'U', 'G': 'FF', 'H': 'kk',
    };

    const isListeningIdle = isSpeaking && currentViseme === 'X' && !isLoading;
    const visemeKey = isSpeaking ? currentViseme : 'X';
    const shapeKey = isListeningIdle ? listeningShape : (apiVisemeToShapeKey[visemeKey] || 'sil');
    const mouthShape = visemeShapes[shapeKey] || visemeShapes['sil'];

    const sizeClasses = size === 'large' ? 'w-64 h-64 border-2' : 'w-12 h-12 border';

    let animationClass = '';
    let glowClass = 'shadow-none';

    if (size === 'large') {
        if (isLoading) {
            glowClass = 'animate-glow-pulse';
        } else if (isSpeaking) {
            animationClass = 'animate-floating';
            glowClass = 'shadow-[0_0_40px_rgba(14,165,233,0.7),_0_0_60px_rgba(14,165,233,0.6)]';
        } else {
            animationClass = 'animate-energetic-hover';
        }
    }

    if (size === 'small' && isLoading) {
        return (
            <div className={`${sizeClasses} rounded-full bg-slate-800/20 border-slate-500/30 flex items-center justify-center`}>
                <div className="w-6 h-6 border-2 border-t-sky-400 border-r-sky-400 border-b-sky-400 border-l-transparent rounded-full animate-spin"></div>
            </div>
        );
    }

    const pupilSize = size === 'large' ? 1.5 : 0.8;
    const eyeSize = { cx: size === 'large' ? 14 : 13.5, r: size === 'large' ? 3 : 2.5 };
    const eyeSize2 = { cx: size === 'large' ? 26 : 26.5, r: size === 'large' ? 3 : 2.5 };
    const highlightSize = size === 'large' ? 0.7 : 0.4;
    const highlightPos = { x: 0.7, y: -0.7 };

    return (
        <div
            ref={avatarRef}
            className={`${sizeClasses} rounded-full bg-slate-800/20 flex items-center justify-center border-slate-500/30 transition-all duration-500 relative overflow-hidden ${animationClass} ${glowClass}`}
        >
            {/* Animated background aurora blobs - Original style */}
            <div className={`absolute inset-0 w-full h-full filter transition-all duration-500 ${size === 'large' ? 'blur-xl' : 'blur-sm'}`}>
                <div
                    className={`absolute w-3/4 h-3/4 bg-gradient-to-tr from-teal-400 to-transparent rounded-full -translate-x-1/4 -translate-y-1/4 transition-transform duration-300 ${isSpeaking ? 'scale-140' : 'scale-100'}`}
                    style={{ animation: 'aurora-1 12s infinite alternate ease-in-out' }}
                />
                <div
                    className={`absolute w-3/4 h-3/4 bg-gradient-to-bl from-sky-500 to-transparent rounded-full translate-x-1/4 translate-y-1/4 transition-transform duration-300 ${isSpeaking ? 'scale-140' : 'scale-100'}`}
                    style={{ animation: 'aurora-2 15s infinite alternate ease-in-out' }}
                />
                <div
                    className={`absolute w-1/2 h-1/2 bg-gradient-to-br from-indigo-500 to-transparent rounded-full -translate-x-1/4 translate-y-1/4 transition-transform duration-300 ${isSpeaking ? 'scale-160' : 'scale-100'}`}
                    style={{ animation: 'aurora-3 10s infinite alternate ease-in-out' }}
                />
            </div>

            {/* Sound wave effect when speaking */}
            {size === 'large' && isSpeaking && !isLoading && (
                <>
                    <div className="absolute inset-0 rounded-full border border-cyan-400/30 animate-sound-wave pointer-events-none" />
                    <div className="absolute inset-0 rounded-full border border-teal-400/20 animate-sound-wave-delay-1 pointer-events-none" />
                </>
            )}

            <svg viewBox="0 0 40 40" className="w-full h-full relative z-10">
                {/* Thinking indicator */}
                {isLoading && size === 'large' && (
                    <circle cx="20" cy="10" r="2" fill="rgba(255,255,255,0.7)" className="animate-thinking-pulse" />
                )}

                {/* Eyes */}
                <g className={`transition-opacity duration-300 ${isLoading ? 'opacity-0' : 'opacity-100'}`}>
                    {/* Left Eye */}
                    <g className={`eye ${!isSpeaking && !isLoading && size === 'large' ? 'animate-subtle-glance' : ''}`}>
                        <path
                            d={`M ${eyeSize.cx - eyeSize.r},15.5 A ${eyeSize.r},${eyeSize.r} 0 0,1 ${eyeSize.cx + eyeSize.r},15.5 C ${eyeSize.cx + eyeSize.r - 1},17.5 ${eyeSize.cx - eyeSize.r + 1},17.5 ${eyeSize.cx - eyeSize.r},15.5 Z`}
                            fill="white"
                        />
                        <g transform={`translate(${pupilTransform.x}, ${pupilTransform.y})`} className="transition-transform duration-75 ease-out">
                            <circle cx={eyeSize.cx} cy="15" r={pupilSize} fill="#1f2937" />
                            <circle cx={eyeSize.cx + highlightPos.x} cy={15 + highlightPos.y} r={highlightSize} fill="white" fillOpacity="0.9" />
                        </g>
                    </g>

                    {/* Right Eye */}
                    <g className={`eye ${!isSpeaking && !isLoading && size === 'large' ? 'animate-subtle-glance' : ''}`} style={{ animationDelay: '0.2s' }}>
                        <path
                            d={`M ${eyeSize2.cx - eyeSize2.r},15.5 A ${eyeSize2.r},${eyeSize2.r} 0 0,1 ${eyeSize2.cx + eyeSize2.r},15.5 C ${eyeSize2.cx + eyeSize2.r - 1},17.5 ${eyeSize2.cx - eyeSize2.r + 1},17.5 ${eyeSize2.cx - eyeSize2.r},15.5 Z`}
                            fill="white"
                        />
                        <g transform={`translate(${pupilTransform.x}, ${pupilTransform.y})`} className="transition-transform duration-75 ease-out">
                            <circle cx={eyeSize2.cx} cy="15" r={pupilSize} fill="#1f2937" />
                            <circle cx={eyeSize2.cx + highlightPos.x} cy={15 + highlightPos.y} r={highlightSize} fill="white" fillOpacity="0.9" />
                        </g>
                    </g>
                </g>

                {/* Closed eyes when loading */}
                {isLoading && size === 'large' && (
                    <g>
                        <path d="M 11.5 16 C 13 17.5, 15 17.5, 16.5 16" stroke="white" strokeWidth="1.5" fill="none" strokeLinecap="round" />
                        <path d="M 23.5 16 C 25 17.5, 27 17.5, 28.5 16" stroke="white" strokeWidth="1.5" fill="none" strokeLinecap="round" />
                    </g>
                )}

                {/* Mouth */}
                <g className={`transition-opacity duration-300 ${isLoading ? 'opacity-0' : 'opacity-100'}`}>
                    <path
                        d={mouthShape.lips}
                        fill="white"
                        style={{ transition: 'all 0.12s cubic-bezier(0.4, 0, 0.2, 1)' }}
                    />
                    <path
                        d={mouthShape.inner || 'M 20 23 L 20 23'}
                        fill="white"
                        fillOpacity={mouthShape.inner ? 0.4 : 0}
                        style={{ transition: 'all 0.12s cubic-bezier(0.4, 0, 0.2, 1)' }}
                    />
                </g>

                {/* Thinking mouth */}
                {isLoading && size === 'large' && (
                    <path
                        d="M 16 24 Q 20 26, 24 24"
                        stroke="white"
                        strokeWidth="1.5"
                        fill="none"
                        strokeLinecap="round"
                        className="opacity-80"
                    />
                )}
            </svg>
        </div>
    );
};