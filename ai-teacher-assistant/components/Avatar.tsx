import React, { useMemo, useState, useEffect, useRef } from 'react';

interface AvatarProps {
    isSpeaking: boolean;
    isLoading: boolean;
    currentViseme: string;
    size?: 'large' | 'small';
}

// Redesigned, multi-part viseme shapes for a more realistic and expressive mouth.
// Includes 'lips' for the outer shape and an optional 'inner' path for details like teeth or tongue.
const visemeShapes: { [key: string]: { lips: string; inner?: string } } = {
    // A gentle, friendly, closed smile. Made more expressive.
    'sil': { lips: 'M 13 22.5 Q 20 27, 27 22.5 Q 20 26.5, 13 22.5 Z' },
    // Lips pressed together, a thin, slightly curved line.
    'PP': { lips: 'M 12 22.5 Q 20 23.5, 28 22.5 Q 20 23, 12 22.5 Z' },
    // Upper teeth touching a curved lower lip.
    'FF': {
        lips: 'M 12 21 C 14 28, 26 28, 28 21 C 26 22, 14 22, 12 21 Z',
        inner: 'M 14 21.5 H 26 V 23 H 14 Z' // Inner path representing teeth line
    },
    // Tongue peeking between lips.
    'TH': {
        lips: 'M 13 20.5 C 16 26.5, 24 26.5, 27 20.5 Q 20 22.5, 13 20.5 Z',
        inner: 'M 16 22.5 Q 20 24.5, 24 22.5 Q 20 24, 16 22.5 Z' // Tongue tip
    },
    // Mouth slightly open, showing line between teeth.
    'DD': {
        lips: 'M 13 19.5 C 16 27, 24 27, 27 19.5 C 24 21, 16 21, 13 19.5 Z',
        inner: 'M 14 23 H 26 V 23.5 H 14 Z'
    },
    // Open mouth for 'k', 'g', showing base of tongue.
    'kk': {
        lips: 'M 14 19 C 17 28, 23 28, 26 19 C 23 21, 17 21, 14 19 Z',
        inner: 'M 16 24 Q 20 26, 24 24 Q 20 25.5, 16 24 Z' // Tongue base
    },
    // Pursed lips for 'ch', 'j'.
    'CH': { lips: 'M 15 20.5 Q 20 27, 25 20.5 Q 20 26.5, 15 20.5 Z' },
    // Wide smile showing teeth line.
    'SS': {
        lips: 'M 11 22 C 15 26, 25 26, 29 22 C 25 23, 15 23, 11 22 Z',
        inner: 'M 13 23 H 27 V 23.5 H 13 Z' // Teeth line
    },
    // Open mouth, tongue raised for 'n'.
    'nn': {
        lips: 'M 13 19 C 17 27, 23 27, 27 19 C 23 21, 17 21, 13 19 Z',
        inner: 'M 15 21 Q 20 19, 25 21 L 24 24 L 16 24 Z' // Raised tongue
    },
    // Rounded lips, small opening.
    'RR': { lips: 'M 16 21 A 4 3 0 1 1 24 21 A 4 3 0 1 1 16 21 Z' },
    // 'ah' sound, a tall, relaxed oval.
    'aa': { lips: 'M 15 19 Q 20 29, 25 19 Q 20 28, 15 19 Z' },
    // 'eh' sound, a wide, soft oval.
    'E': { lips: 'M 12 20.5 C 17 27, 23 27, 28 20.5 C 23 22, 17 22, 12 20.5 Z' },
    // 'ih' sound, less open than 'eh'.
    'I': { lips: 'M 13 20 C 17 26, 23 26, 27 20 C 23 21.5, 17 21.5, 13 20 Z' },
    // 'oh' sound, a rounded, slightly taller oval.
    'O': { lips: 'M 16 19.5 Q 20 16, 24 19.5 Q 20 26.5, 16 19.5 Z' },
    // 'oo' sound, a small, tall 'o' shape.
    'U': { lips: 'M 17.5 20 A 2.5 4 0 1 1 22.5 20 A 2.5 4 0 1 1 17.5 20 Z' },
};


export const Avatar: React.FC<AvatarProps> = ({ isSpeaking, isLoading, currentViseme, size = 'large' }) => {
    const avatarRef = useRef<HTMLDivElement>(null);
    const [pupilTransform, setPupilTransform] = useState({ x: 0, y: 0 });
    const [listeningShape, setListeningShape] = useState('sil');

    useEffect(() => {
        let animationTimeout: ReturnType<typeof setTimeout>;

        // This effect creates a subtle mouth animation loop for the "listening" state to make the avatar feel more alive.
        if (isSpeaking && currentViseme === 'X' && !isLoading) {
            const sequence = ['sil', 'PP', 'sil', 'I', 'sil', 'sil', 'CH', 'sil']; // 'sil' is more frequent
            const animateMouth = () => {
                const nextShape = sequence[Math.floor(Math.random() * sequence.length)];
                setListeningShape(nextShape);
                
                // Random delay for a more natural, less robotic feel
                const delay = (nextShape === 'sil' ? 2000 : 200) + Math.random() * 1000;
                animationTimeout = setTimeout(animateMouth, delay);
            };

            // Start animation after a short initial delay
            animationTimeout = setTimeout(animateMouth, 1500);

        } else {
            setListeningShape('sil'); // Reset to default smile when not in the idle listening state
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
            
            const MAX_DISTANCE = 300; // The distance from center at which pupils are at max offset
            const MAX_PUPIL_OFFSET = size === 'large' ? 1.5 : 0.8; // Max travel distance in SVG units

            const movementScale = Math.min(1, distance / MAX_DISTANCE);
            
            const pupilX = Math.cos(angle) * MAX_PUPIL_OFFSET * movementScale;
            const pupilY = Math.sin(angle) * MAX_PUPIL_OFFSET * movementScale;

            setPupilTransform({ x: pupilX, y: pupilY });
        };

        window.addEventListener('mousemove', handleMouseMove);

        return () => {
            window.removeEventListener('mousemove', handleMouseMove);
        };
    }, [size]);

    // Improved mapping from limited API viseme codes to our expressive shapes.
    const apiVisemeToShapeKey: { [key: string]: string } = {
        'X': 'sil', // Silence, neutral smile
        'A': 'aa',  // Open mouth, 'ah'
        'B': 'PP',  // Closed lips, 'm', 'b', 'p'
        'C': 'SS',  // Wide smile/teeth, for 's', 'c' sounds
        'D': 'DD',  // Teeth together, for 'd', 't'
        'E': 'E',   // Wide open, 'eh'
        'F': 'U',   // Small rounded mouth, 'oo', 'w'
        'G': 'FF',  // Teeth on lip, 'f', 'v'
        'H': 'kk',  // Open back of mouth, 'k', 'g'
    };
    
    // Logic to select the correct mouth shape based on state
    const isListeningIdle = isSpeaking && currentViseme === 'X' && !isLoading;
    const visemeKey = isSpeaking ? currentViseme : 'X';
    const shapeKey = isListeningIdle ? listeningShape : (apiVisemeToShapeKey[visemeKey] || 'sil');
    const mouthShape = visemeShapes[shapeKey] || visemeShapes['sil'];

    const sizeClasses = size === 'large' ? 'w-64 h-64 border-4' : 'w-12 h-12 border-2';

    let animationClass = '';
    let glowClass = 'shadow-none';
    if (size === 'large') {
        if (isLoading) {
            glowClass = 'animate-glow-pulse';
        } else if (isSpeaking) {
            animationClass = 'animate-floating';
            glowClass = 'shadow-[0_0_40px_rgba(2,179,217,0.8),_0_0_60px_rgba(0,180,255,0.7)]';
        } else {
             animationClass = 'animate-energetic-hover';
        }
    }

    if (size === 'small' && isLoading) {
        return (
             <div className={`${sizeClasses} rounded-full bg-gray-700/50 flex items-center justify-center border-gray-600`}>
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
        <div ref={avatarRef} className={`${sizeClasses} rounded-full bg-gray-700/50 flex items-center justify-center border-gray-600 transition-all duration-500 relative overflow-hidden ${animationClass} ${glowClass}`}>
            <div className={`absolute inset-0 w-full h-full filter transition-all duration-500 ${size === 'large' ? 'blur-xl' : 'blur-sm'}`}>
                <div className={`absolute w-3/4 h-3/4 bg-gradient-to-tr from-teal-400 to-transparent rounded-full -translate-x-1/4 -translate-y-1/4 transition-transform duration-300 ${isSpeaking ? 'scale-140' : 'scale-100'}`} style={{ animation: 'aurora-1 12s infinite alternate ease-in-out' }}></div>
                <div className={`absolute w-3/4 h-3/4 bg-gradient-to-bl from-sky-500 to-transparent rounded-full translate-x-1/4 translate-y-1/4 transition-transform duration-300 ${isSpeaking ? 'scale-140' : 'scale-100'}`} style={{ animation: 'aurora-2 15s infinite alternate ease-in-out' }}></div>
                <div className={`absolute w-1/2 h-1/2 bg-gradient-to-br from-indigo-500 to-transparent rounded-full -translate-x-1/4 translate-y-1/4 transition-transform duration-300 ${isSpeaking ? 'scale-160' : 'scale-100'}`} style={{ animation: 'aurora-3 10s infinite alternate ease-in-out' }}></div>
            </div>

            <svg viewBox="0 0 40 40" className="w-full h-full relative z-10">
                {isLoading && size === 'large' && (
                    <circle cx="20" cy="10" r="2" fill="rgba(255,255,255,0.7)" className="animate-thinking-pulse" />
                )}

                {/* Eyes */}
                <g className={`transition-opacity duration-300 ${isLoading ? 'opacity-0' : 'opacity-100'}`}>
                    <g className={`eye ${!isSpeaking && !isLoading && size === 'large' ? 'animate-subtle-glance' : ''}`}>
                        <path d={`M ${eyeSize.cx-eyeSize.r},15.5 A ${eyeSize.r},${eyeSize.r} 0 0,1 ${eyeSize.cx+eyeSize.r},15.5 C ${eyeSize.cx+eyeSize.r-1},17.5 ${eyeSize.cx-eyeSize.r+1},17.5 ${eyeSize.cx-eyeSize.r},15.5 Z`} fill="white" />
                        <g transform={`translate(${pupilTransform.x}, ${pupilTransform.y})`} className="transition-transform duration-75 ease-out">
                            <circle cx={eyeSize.cx} cy="15" r={pupilSize} fill="#1f2937" />
                            <circle cx={eyeSize.cx + highlightPos.x} cy={15 + highlightPos.y} r={highlightSize} fill="white" fillOpacity="0.9" />
                        </g>
                    </g>
                     <g className={`eye ${!isSpeaking && !isLoading && size === 'large' ? 'animate-subtle-glance' : ''}`} style={{ animationDelay: '0.2s' }}>
                        <path d={`M ${eyeSize2.cx-eyeSize2.r},15.5 A ${eyeSize2.r},${eyeSize2.r} 0 0,1 ${eyeSize2.cx+eyeSize2.r},15.5 C ${eyeSize2.cx+eyeSize2.r-1},17.5 ${eyeSize2.cx-eyeSize2.r+1},17.5 ${eyeSize2.cx-eyeSize2.r},15.5 Z`} fill="white" />
                        <g transform={`translate(${pupilTransform.x}, ${pupilTransform.y})`} className="transition-transform duration-75 ease-out">
                            <circle cx={eyeSize2.cx} cy="15" r={pupilSize} fill="#1f2937" />
                            <circle cx={eyeSize2.cx + highlightPos.x} cy={15 + highlightPos.y} r={highlightSize} fill="white" fillOpacity="0.9" />
                        </g>
                    </g>
                </g>
                
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
                        className="transition-all duration-200 ease-out"
                    />
                    {/* Inner mouth path for details like teeth/tongue. Transitions opacity and shape smoothly. */}
                    <path
                        d={mouthShape.inner || 'M 20 23 L 20 23'}
                        fill="white"
                        fillOpacity={mouthShape.inner ? 0.4 : 0}
                        className="transition-all duration-200 ease-out"
                    />
                </g>
            </svg>
        </div>
    );
};