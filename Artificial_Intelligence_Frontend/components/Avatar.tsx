import React, { useEffect, useState, useRef } from 'react';

interface AvatarProps {
    isSpeaking: boolean;
    isLoading: boolean;
    currentViseme: string;
    size?: 'large' | 'small';
}

// ============================================================================
// MODERN 2025 AI AVATAR - Ultra-Smooth Cross-Fade Transitions
// Uses CSS keyframes + layered cross-fade for buttery smooth state changes
// ============================================================================

type AvatarState = 'idle' | 'loading' | 'speaking';

interface ColorTheme {
    primary: string;
    secondary: string;
    tertiary: string;
    glow: string;
}

const COLOR_THEMES: Record<AvatarState, ColorTheme> = {
    idle: {
        primary: '#22d3ee',      // cyan-400
        secondary: '#38bdf8',    // sky-400
        tertiary: '#3b82f6',     // blue-500
        glow: 'rgba(34, 211, 238, 0.4)'
    },
    loading: {
        primary: '#a855f7',      // purple-500
        secondary: '#d946ef',    // fuchsia-500
        tertiary: '#8b5cf6',     // violet-500
        glow: 'rgba(168, 85, 247, 0.4)'
    },
    speaking: {
        primary: '#2dd4bf',      // teal-400
        secondary: '#34d399',    // emerald-400
        tertiary: '#22d3ee',     // cyan-400
        glow: 'rgba(45, 212, 191, 0.5)'
    }
};

const ANIMATION_SPEEDS: Record<AvatarState, { morph: string; rotate: string; pulse: string }> = {
    idle: { morph: '10s', rotate: '20s', pulse: '5s' },
    loading: { morph: '5s', rotate: '10s', pulse: '2.5s' },
    speaking: { morph: '4s', rotate: '8s', pulse: '2s' }
};

// Transition duration for cross-fade (in ms)
const TRANSITION_DURATION = 1200;

export const Avatar: React.FC<AvatarProps> = ({ isSpeaking, isLoading, size = 'large' }) => {
    // State management for smooth cross-fade
    const [layers, setLayers] = useState<{ state: AvatarState; opacity: number; key: number }[]>([
        { state: 'idle', opacity: 1, key: 0 }
    ]);
    const keyCounter = useRef(1);
    const transitionTimeoutRef = useRef<NodeJS.Timeout | null>(null);

    // Determine target state
    const targetState: AvatarState = isLoading ? 'loading' : isSpeaking ? 'speaking' : 'idle';

    // Handle state transitions
    useEffect(() => {
        const currentTopLayer = layers[layers.length - 1];

        if (currentTopLayer.state !== targetState) {
            // Add new layer on top with opacity 0
            const newKey = keyCounter.current++;
            setLayers(prev => [
                ...prev.map(l => ({ ...l })), // Keep existing layers
                { state: targetState, opacity: 0, key: newKey }
            ]);

            // Animate: fade in new layer, fade out old layers
            requestAnimationFrame(() => {
                setTimeout(() => {
                    setLayers(prev => prev.map((l, i) => ({
                        ...l,
                        opacity: i === prev.length - 1 ? 1 : 0 // Top layer fully visible, others fade out
                    })));
                }, 50); // Small delay to ensure CSS picks up the change
            });

            // Clean up old layers after transition
            if (transitionTimeoutRef.current) {
                clearTimeout(transitionTimeoutRef.current);
            }
            transitionTimeoutRef.current = setTimeout(() => {
                setLayers(prev => [prev[prev.length - 1]]); // Keep only the top layer
            }, TRANSITION_DURATION + 100);
        }

        return () => {
            if (transitionTimeoutRef.current) {
                clearTimeout(transitionTimeoutRef.current);
            }
        };
    }, [targetState]);

    // Inject keyframes
    useEffect(() => {
        const styleId = 'avatar-keyframes-v3';
        if (!document.getElementById(styleId)) {
            const style = document.createElement('style');
            style.id = styleId;
            style.textContent = `
                @keyframes morphBlob {
                    0%, 100% {
                        border-radius: 60% 40% 30% 70% / 60% 30% 70% 40%;
                        transform: rotate(0deg) scale(1);
                    }
                    25% {
                        border-radius: 30% 60% 70% 40% / 50% 60% 30% 60%;
                        transform: rotate(90deg) scale(1.015);
                    }
                    50% {
                        border-radius: 50% 60% 30% 60% / 30% 60% 70% 40%;
                        transform: rotate(180deg) scale(0.985);
                    }
                    75% {
                        border-radius: 60% 40% 60% 50% / 70% 30% 50% 60%;
                        transform: rotate(270deg) scale(1.01);
                    }
                }

                @keyframes morphBlobAlt {
                    0%, 100% {
                        border-radius: 40% 60% 60% 40% / 70% 30% 70% 30%;
                        transform: rotate(0deg) scale(1);
                    }
                    33% {
                        border-radius: 70% 30% 50% 50% / 30% 70% 30% 70%;
                        transform: rotate(-60deg) scale(1.02);
                    }
                    66% {
                        border-radius: 30% 70% 40% 60% / 50% 40% 60% 50%;
                        transform: rotate(-120deg) scale(0.98);
                    }
                }

                @keyframes gentlePulse {
                    0%, 100% { opacity: 0.5; transform: scale(1); }
                    50% { opacity: 0.7; transform: scale(1.03); }
                }

                @keyframes slowRotate {
                    0% { transform: rotate(0deg); }
                    100% { transform: rotate(360deg); }
                }

                @keyframes floatY {
                    0%, 100% { transform: translateY(0px); }
                    50% { transform: translateY(-6px); }
                }

                @keyframes innerGlow {
                    0%, 100% { opacity: 0.35; }
                    50% { opacity: 0.6; }
                }
            `;
            document.head.appendChild(style);
        }
    }, []);

    // Size config
    const sizeConfig = size === 'large'
        ? { container: 'w-48 h-48', blob: 140, glow: 200 }
        : { container: 'w-10 h-10', blob: 36, glow: 50 };

    // Small loading state
    if (size === 'small' && isLoading) {
        return (
            <div className={`${sizeConfig.container} rounded-full bg-slate-800/20 border-slate-500/30 flex items-center justify-center`}>
                <div className="w-6 h-6 border-2 border-t-sky-400 border-r-sky-400 border-b-sky-400 border-l-transparent rounded-full animate-spin"></div>
            </div>
        );
    }

    // Render a single blob layer
    const renderBlobLayer = (state: AvatarState, opacity: number, layerKey: number) => {
        const colors = COLOR_THEMES[state];
        const durations = ANIMATION_SPEEDS[state];

        return (
            <div
                key={layerKey}
                className="absolute inset-0 flex items-center justify-center pointer-events-none"
                style={{
                    opacity,
                    transition: `opacity ${TRANSITION_DURATION}ms cubic-bezier(0.25, 0.1, 0.25, 1.0)`,
                }}
            >
                {/* Outer Glow */}
                <div
                    className="absolute rounded-full"
                    style={{
                        width: `${sizeConfig.glow}px`,
                        height: `${sizeConfig.glow}px`,
                        background: `radial-gradient(circle, ${colors.glow} 0%, transparent 70%)`,
                        animation: `gentlePulse ${durations.pulse} ease-in-out infinite`,
                        filter: 'blur(25px)',
                    }}
                />

                {/* Rotating conic glow */}
                <div
                    className="absolute rounded-full"
                    style={{
                        width: `${sizeConfig.blob * 1.35}px`,
                        height: `${sizeConfig.blob * 1.35}px`,
                        background: `conic-gradient(from 0deg, ${colors.primary}30, ${colors.secondary}30, ${colors.tertiary}30, ${colors.primary}30)`,
                        animation: `slowRotate ${durations.rotate} linear infinite`,
                        filter: 'blur(18px)',
                        opacity: 0.5,
                    }}
                />

                {/* Main Blob */}
                <div
                    className="absolute"
                    style={{
                        width: `${sizeConfig.blob}px`,
                        height: `${sizeConfig.blob}px`,
                        background: `linear-gradient(135deg, ${colors.primary} 0%, ${colors.secondary} 50%, ${colors.tertiary} 100%)`,
                        animation: `morphBlob ${durations.morph} ease-in-out infinite`,
                        boxShadow: `
                            inset 0 0 40px rgba(255,255,255,0.25),
                            inset -12px -12px 40px rgba(0,0,0,0.15),
                            0 0 50px ${colors.glow}
                        `,
                    }}
                />

                {/* Secondary overlay blob for depth */}
                <div
                    className="absolute"
                    style={{
                        width: `${sizeConfig.blob * 0.88}px`,
                        height: `${sizeConfig.blob * 0.88}px`,
                        background: `linear-gradient(315deg, ${colors.secondary}bb 0%, ${colors.primary}bb 100%)`,
                        animation: `morphBlobAlt ${durations.morph} ease-in-out infinite`,
                        animationDelay: '-2.5s',
                        mixBlendMode: 'overlay',
                        opacity: 0.7,
                    }}
                />

                {/* Inner highlight - glass effect */}
                <div
                    className="absolute rounded-full"
                    style={{
                        width: `${sizeConfig.blob * 0.55}px`,
                        height: `${sizeConfig.blob * 0.45}px`,
                        background: `radial-gradient(ellipse at 30% 30%, rgba(255,255,255,0.45) 0%, transparent 70%)`,
                        top: size === 'large' ? '22%' : '12%',
                        left: size === 'large' ? '22%' : '12%',
                        animation: `innerGlow ${durations.pulse} ease-in-out infinite`,
                        borderRadius: '50%',
                        transform: 'rotate(-25deg)',
                    }}
                />

                {/* Subtle core glow */}
                <div
                    className="absolute rounded-full pointer-events-none"
                    style={{
                        width: `${sizeConfig.blob * 0.35}px`,
                        height: `${sizeConfig.blob * 0.35}px`,
                        background: `radial-gradient(circle, ${colors.primary}70 0%, transparent 70%)`,
                        filter: 'blur(12px)',
                        opacity: state === 'speaking' ? 0.85 : 0.55,
                    }}
                />
            </div>
        );
    };

    return (
        <div
            className={`${sizeConfig.container} relative flex items-center justify-center`}
            style={{
                animation: size === 'large' ? `floatY 8s ease-in-out infinite` : 'none'
            }}
        >
            {/* Render all active layers - older layers fade out, newest fades in */}
            {layers.map(layer => renderBlobLayer(layer.state, layer.opacity, layer.key))}
        </div>
    );
};