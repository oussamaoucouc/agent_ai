import React, { useMemo, useState, useEffect, useRef } from 'react';

interface AvatarProps {
    isSpeaking: boolean;
    isLoading: boolean;
    currentViseme: string;
    size?: 'large' | 'small';
}

// Redesigned viseme shapes to be more organic and natural.
const visemeShapes: { [key: string]: string } = {
    // A gentle, friendly, closed smile
    'sil': 'M 12 21 C 15 24, 25 24, 28 21 C 26 23.5, 14 23.5, 12 21 Z',
    // Lips pressed together
    'PP': 'M 12 21.5 L 28 21.5 C 27 22.5, 13 22.5, 12 21.5 Z',
    // Upper teeth touching lower lip
    'FF': 'M 12 20 L 28 20 C 26 25, 14 25, 12 20 Z',
    // Slightly open mouth, tongue visible
    'TH': 'M 13 20.5 C 16 23.5, 24 23.5, 27 20.5 C 24 22.5, 16 22.5, 13 20.5 Z',
    // A bit more open
    'DD': 'M 13 19.5 C 16 25.5, 24 25.5, 27 19.5 C 24 24.5, 16 24.5, 13 19.5 Z',
    // Open mouth for 'k' 'g' sounds
    'kk': 'M 14 19 C 17 26, 23 26, 26 19 C 23 25, 17 25, 14 19 Z',
    // Pursed lips for 'ch', 'j'
    'CH': 'M 14 19.5 C 16 25, 24 25, 26 19.5 C 24 24, 16 24, 14 19.5 Z',
    // Wide, thin smile for 's' sounds
    'SS': 'M 11 21.5 C 15 24, 25 24, 29 21.5 C 26 23, 14 23, 11 21.5 Z',
    // Generic open mouth for 'n'
    'nn': 'M 13 19 C 17 26, 23 26, 27 19 C 23 25, 17 25, 13 19 Z',
    // Rounded lips, small opening
    'RR': 'M 16.5 20.5 A 3 3 0 1 1 23.5 20.5 A 3 3 0 1 1 16.5 20.5 Z',
    // 'ah' sound, a tall, relaxed oval
    'aa': 'M 15 19 Q 20 28, 25 19 Q 20 27, 15 19 Z',
    // 'eh' sound, a wide, soft oval
    'E': 'M 12 20.5 C 17 26, 23 26, 28 20.5 C 23 25, 17 25, 12 20.5 Z',
    // 'ih' sound, less open than 'eh'
    'I': 'M 13 20 C 17 25, 23 25, 27 20 C 23 24, 17 24, 13 20 Z',
    // 'oh' sound, a rounded, slightly taller oval
    'O': 'M 17 19.5 Q 20 17, 23 19.5 Q 20 25, 17 19.5 Z',
    // 'oo' sound, a small, tall 'o' shape
    'U': 'M 17.5 20 A 2.5 4 0 1 1 22.5 20 A 2.5 4 0 1 1 17.5 20 Z',
};

export const Avatar: React.FC<AvatarProps> = ({ isSpeaking, isLoading, currentViseme, size = 'large' }) => {
    const avatarRef = useRef<HTMLDivElement>(null);
    const [pupilTransform, setPupilTransform] = useState({ x: 0, y: 0 });

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

    const apiVisemeToShapeKey: { [key: string]: string } = {
        'X': 'sil', 'A': 'aa', 'B': 'PP', 'C': 'E', 'D': 'TH',
        'E': 'O', 'F': 'U', 'G': 'FF', 'H': 'kk',
    };

    const visemeKey = isSpeaking ? currentViseme : 'X';
    const shapeKey = apiVisemeToShapeKey[visemeKey] || 'sil';
    const mouthPath = visemeShapes[shapeKey] || visemeShapes['sil'];

    const sizeClasses = size === 'large' ? 'w-64 h-64 border-4' : 'w-12 h-12 border-2';

    let animationClass = '';
    let glowClass = 'shadow-none';
    if (size === 'large' && !isLoading) {
        animationClass = isSpeaking ? 'animate-floating' : 'animate-energetic-hover';
        glowClass = isSpeaking
            ? 'shadow-[0_0_40px_rgba(2,179,217,0.8),_0_0_60px_rgba(0,180,255,0.7)]'
            : 'shadow-none';
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
                    <g className="eye">
                        <path d={`M ${eyeSize.cx-eyeSize.r},15.5 A ${eyeSize.r},${eyeSize.r} 0 0,1 ${eyeSize.cx+eyeSize.r},15.5 C ${eyeSize.cx+eyeSize.r-1},17.5 ${eyeSize.cx-eyeSize.r+1},17.5 ${eyeSize.cx-eyeSize.r},15.5 Z`} fill="white" />
                        <g transform={`translate(${pupilTransform.x}, ${pupilTransform.y})`} className="transition-transform duration-75 ease-out">
                            <circle cx={eyeSize.cx} cy="15" r={pupilSize} fill="#1f2937" />
                            <circle cx={eyeSize.cx + highlightPos.x} cy={15 + highlightPos.y} r={highlightSize} fill="white" fillOpacity="0.9" />
                        </g>
                    </g>
                     <g className="eye" style={{ animationDelay: '0.2s' }}>
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
                    <path d={mouthPath} fill="white" className="transition-all duration-100" />
                </g>
            </svg>
        </div>
    );
};