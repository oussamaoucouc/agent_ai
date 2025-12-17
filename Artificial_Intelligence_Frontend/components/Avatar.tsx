import React, { useState, useEffect, useRef } from 'react';

interface AvatarProps {
    isSpeaking: boolean;
    isLoading: boolean;
    currentViseme: string;
    size?: 'large' | 'small';
}

export const Avatar: React.FC<AvatarProps> = ({ isSpeaking, isLoading, currentViseme, size = 'large' }) => {
    // -------------------------------------------------------------------------
    //  FLUID BLOB IMPLEMENTATION (Metaballs Animation)
    // -------------------------------------------------------------------------
    //  Core Concept: Multiple orbiting circles are blurred together using an
    //  SVG filter (feGaussianBlur + feColorMatrix) to create a "liquid"
    //  merging effect.
    // -------------------------------------------------------------------------

    const containerRef = useRef<HTMLDivElement>(null);
    const animationRef = useRef<number | null>(null);

    // Physics state for blobs
    // We use a central blob + orbiting satellites
    const blobCount = 5;
    const blobs = useRef(Array.from({ length: blobCount }).map((_, i) => ({
        x: 0,
        y: 0,
        vx: (Math.random() - 0.5) * 2,
        vy: (Math.random() - 0.5) * 2,
        radius: i === 0 ? 35 : 15 + Math.random() * 15, // Index 0 is the "Core"
        color: '', // Set dynamically
        angle: Math.random() * Math.PI * 2,
        speed: 0.02 + Math.random() * 0.03
    })));

    // Dynamic Colors based on state
    const [gradientClass, setGradientClass] = useState('from-cyan-400 to-blue-600');
    const [glowColor, setGlowColor] = useState('rgba(34, 211, 238, 0.5)'); // Cyan default

    // Update styling based on state
    useEffect(() => {
        if (isLoading) {
            setGradientClass('from-violet-400 to-fuchsia-600'); // Purple/Pink thinking
            setGlowColor('rgba(192, 38, 211, 0.5)');
        } else if (isSpeaking) {
            setGradientClass('from-emerald-300 to-teal-500'); // Active Green/Teal
            setGlowColor('rgba(45, 212, 191, 0.6)');
        } else {
            setGradientClass('from-cyan-400 to-blue-600'); // Neutral Blue
            setGlowColor('rgba(34, 211, 238, 0.5)');
        }
    }, [isLoading, isSpeaking]);

    // MAIN ANIMATION LOOP
    useEffect(() => {
        let time = 0;

        const animate = () => {
            time += 0.05;

            // Adjust physics parameters based on state
            const excitement = isSpeaking ? 2.5 : isLoading ? 0.5 : 1.0;
            const radiusScale = isSpeaking ? 1.2 : 1.0;
            const centerWander = isLoading ? 5 : 2; // Core moves more when thinking

            blobs.current.forEach((blob, i) => {
                // Blob 0 is the CORE
                if (i === 0) {
                    // Gentle wandering center
                    blob.x = Math.sin(time * 0.5) * centerWander;
                    blob.y = Math.cos(time * 0.3) * centerWander;
                    // Pulse size
                    if (isSpeaking) {
                        blob.radius = 35 + Math.sin(time * 10) * 3; // Rapid pulse
                    } else if (isLoading) {
                        blob.radius = 30 + Math.sin(time * 3) * 5; // Deep pulse
                    } else {
                        blob.radius = 35 + Math.sin(time) * 2; // Idle breath
                    }
                }
                // Creating Orbiting Satellites
                else {
                    // Update angle
                    blob.angle += blob.speed * excitement;

                    // Radius from center varies
                    const orbitRadius = (40 + Math.sin(time * i + i) * 10) * radiusScale;

                    // Simple orbital mechanics
                    blob.x = Math.cos(blob.angle) * orbitRadius;
                    blob.y = Math.sin(blob.angle) * orbitRadius;
                }
            });

            // Force Re-render / Update DOM
            // We use direct DOM manipulation for performance (avoiding React render cycle for 60fps)
            if (containerRef.current) {
                const childDivs = containerRef.current.children;
                blobs.current.forEach((blob, i) => {
                    const el = childDivs[i] as HTMLElement;
                    if (el) {
                        el.style.transform = `translate(${blob.x}px, ${blob.y}px)`;
                        el.style.width = `${blob.radius * 2}px`;
                        el.style.height = `${blob.radius * 2}px`;
                        // Centering correction
                        el.style.marginLeft = `-${blob.radius}px`;
                        el.style.marginTop = `-${blob.radius}px`;
                    }
                });
            }

            animationRef.current = requestAnimationFrame(animate);
        };

        animationRef.current = requestAnimationFrame(animate);

        return () => {
            if (animationRef.current) cancelAnimationFrame(animationRef.current);
        };
    }, [isSpeaking, isLoading]);


    // Determine Size Classes
    const sizeClasses = size === 'large' ? 'w-48 h-48' : 'w-10 h-10';
    const filterId = `goo-filter-${size}`; // Unique ID

    // Loading Spinner for small size
    if (size === 'small' && isLoading) {
        return (
            <div className={`${sizeClasses} rounded-full bg-slate-800/20 border-slate-500/30 flex items-center justify-center`}>
                <div className="w-6 h-6 border-2 border-t-sky-400 border-r-sky-400 border-b-sky-400 border-l-transparent rounded-full animate-spin"></div>
            </div>
        );
    }

    return (
        <div className="relative flex items-center justify-center">

            {/* 1. THE GOOEY CONTAINER */}
            <div
                className={`${sizeClasses} relative flex items-center justify-center transition-all duration-700`}
                style={{ filter: `url(#${filterId})` }} // Apply the SVG filter here
            >
                <div ref={containerRef} className="absolute inset-0 flex items-center justify-center">
                    {blobs.current.map((_, i) => (
                        <div
                            key={i}
                            className={`absolute rounded-full bg-linear-to-br ${gradientClass} transition-colors duration-700`}
                            style={{
                                width: '50px',
                                height: '50px',
                                left: '50%',
                                top: '50%',
                                willChange: 'transform, width, height',
                            }}
                        />
                    ))}
                </div>
            </div>

            {/* 2. GLOW EFFECT (Outside the filter to stay soft) */}
            <div
                className={`absolute inset-0 rounded-full blur-2xl transition-all duration-700 opacity-60 pointer-events-none`}
                style={{
                    backgroundColor: glowColor,
                    transform: 'scale(1.2)'
                }}
            />

            {/* 3. SVG FILTER DEFINITION (Hidden) */}
            {/* 
                Explanation: 
                - feGaussianBlur: Blurs the shapes so they overlap.
                - feColorMatrix: Increases slight opacity to 1 (solid) and cuts off transparent edges.
                                 This creates the sharp "liquid" edge where blurred elements meet.
            */}
            <svg style={{ position: 'absolute', width: 0, height: 0, pointerEvents: 'none' }}>
                <defs>
                    <filter id={filterId}>
                        <feGaussianBlur in="SourceGraphic" stdDeviation={size === 'large' ? "12" : "4"} result="blur" />
                        <feColorMatrix
                            in="blur"
                            mode="matrix"
                            values="1 0 0 0 0  0 1 0 0 0  0 0 1 0 0  0 0 0 19 -9"
                            result="goo"
                        />
                        <feComposite in="SourceGraphic" in2="goo" operator="atop" />
                    </filter>
                </defs>
            </svg>
        </div>
    );
};