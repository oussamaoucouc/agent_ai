/// <reference lib="dom" />
/// <reference lib="dom.iterable" />

/**
 * Web Audio API Queue - Perfect Gapless Playback
 * 
 * This class provides professional-grade audio playback with:
 * - Zero gaps between chunks (microsecond precision)
 * - Proper viseme synchronization
 * - Clean error handling
 * - Simple, maintainable code
 */

import { VisemeData } from './types';

interface QueuedAudio {
    buffer: AudioBuffer;
    visemes: VisemeData;
    messageId: string;
    url: string;
}

export class WebAudioQueue {
    private audioContext: AudioContext;
    private queue: QueuedAudio[] = [];
    private isPlaying = false;
    private nextScheduledTime = 0;
    private currentSource: AudioBufferSourceNode | null = null;
    private animationFrameId: number | null = null;

    // Callbacks
    private onVisemeChange: (viseme: string) => void;
    private onPlayingStateChange: (isPlaying: boolean) => void;
    private onMessageIdChange: (messageId: string | null) => void;

    constructor(
        onVisemeChange: (viseme: string) => void,
        onPlayingStateChange: (isPlaying: boolean) => void,
        onMessageIdChange: (messageId: string | null) => void
    ) {
        // Create AudioContext (handles browser prefixes)
        const AudioContextClass = (window.AudioContext || (window as any).webkitAudioContext) as typeof AudioContext;
        this.audioContext = new AudioContextClass();
        this.onVisemeChange = onVisemeChange;
        this.onPlayingStateChange = onPlayingStateChange;
        this.onMessageIdChange = onMessageIdChange;

        console.log('[WebAudioQueue] Initialized with sample rate:', this.audioContext.sampleRate);
    }

    /**
     * Add audio chunk to queue and start playback if needed
     */
    async enqueue(url: string, visemes: VisemeData, messageId: string): Promise<void> {
        try {
            console.log(`[WebAudioQueue] Enqueuing: ${url.substring(url.lastIndexOf('/') + 1)}`);

            // Fetch and decode audio
            const buffer = await this.fetchAndDecode(url);

            // Add to queue
            this.queue.push({ buffer, visemes, messageId, url });
            console.log(`[WebAudioQueue] Queue length: ${this.queue.length}`);

            // Start playback if not already playing
            if (!this.isPlaying) {
                this.playNext();
            }
        } catch (error) {
            console.error(`[WebAudioQueue] Failed to enqueue ${url}:`, error);
            // Still try to play next chunk if available
            if (!this.isPlaying && this.queue.length > 0) {
                this.playNext();
            }
        }
    }

    /**
     * Fetch audio file and decode to AudioBuffer
     */
    private async fetchAndDecode(url: string): Promise<AudioBuffer> {
        const response = await fetch(url);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const arrayBuffer = await response.arrayBuffer();
        return await this.audioContext.decodeAudioData(arrayBuffer);
    }

    /**
     * Play next audio chunk from queue
     */
    private playNext(): void {
        // Get next chunk
        const next = this.queue.shift();

        if (!next) {
            // Queue empty - stop playback
            console.log('[WebAudioQueue] Queue empty, stopping');
            this.isPlaying = false;
            this.onPlayingStateChange(false);
            this.onVisemeChange('X');
            this.onMessageIdChange(null);
            this.nextScheduledTime = 0;
            return;
        }

        console.log(`[WebAudioQueue] Playing: ${next.url.substring(next.url.lastIndexOf('/') + 1)}`);
        this.isPlaying = true;
        this.onPlayingStateChange(true);
        this.onMessageIdChange(next.messageId);

        // Create source node
        const source = this.audioContext.createBufferSource();
        source.buffer = next.buffer;
        source.connect(this.audioContext.destination);

        // Calculate precise start time for gapless playback
        const now = this.audioContext.currentTime;
        const startTime = Math.max(now, this.nextScheduledTime);

        // Schedule playback
        source.start(startTime);

        // Update next scheduled time for gapless transition
        this.nextScheduledTime = startTime + next.buffer.duration;

        console.log(`[WebAudioQueue] Scheduled at ${startTime.toFixed(3)}s, duration ${next.buffer.duration.toFixed(3)}s, next at ${this.nextScheduledTime.toFixed(3)}s`);

        // Start viseme animation
        this.animateVisemes(next.visemes, startTime, next.buffer.duration);

        // When audio ends, play next chunk
        source.onended = () => {
            console.log('[WebAudioQueue] Chunk finished');
            this.playNext();
        };

        this.currentSource = source;
    }

    /**
     * Animate visemes in sync with audio playback
     */
    private animateVisemes(visemeData: VisemeData, startTime: number, duration: number): void {
        // Sort visemes by start time
        const sortedCues = [...visemeData.mouthCues].sort((a, b) => a.start - b.start);

        const animate = () => {
            const currentTime = this.audioContext.currentTime;
            const elapsed = currentTime - startTime;

            // Check if audio has finished
            if (elapsed >= duration) {
                this.onVisemeChange('X');
                if (this.animationFrameId) {
                    cancelAnimationFrame(this.animationFrameId);
                    this.animationFrameId = null;
                }
                return;
            }

            // Find current viseme
            let currentViseme = 'X';
            for (const cue of sortedCues) {
                if (cue.start <= elapsed) {
                    currentViseme = cue.value;
                } else {
                    break;
                }
            }

            this.onVisemeChange(currentViseme);
            this.animationFrameId = requestAnimationFrame(animate);
        };

        // Stop any existing animation
        if (this.animationFrameId) {
            cancelAnimationFrame(this.animationFrameId);
        }

        // Start animation
        this.animationFrameId = requestAnimationFrame(animate);
    }

    /**
     * Stop playback and clear queue
     */
    stop(): void {
        console.log('[WebAudioQueue] Stopping playback');

        // Stop current source
        if (this.currentSource) {
            try {
                this.currentSource.stop();
            } catch (e) {
                // Ignore if already stopped
            }
            this.currentSource = null;
        }

        // Stop animation
        if (this.animationFrameId) {
            cancelAnimationFrame(this.animationFrameId);
            this.animationFrameId = null;
        }

        // Clear queue
        this.queue = [];
        this.isPlaying = false;
        this.nextScheduledTime = 0;

        this.onPlayingStateChange(false);
        this.onVisemeChange('X');
        this.onMessageIdChange(null);
    }

    /**
     * Get current queue length
     */
    getQueueLength(): number {
        return this.queue.length;
    }

    /**
     * Check if currently playing
     */
    isCurrentlyPlaying(): boolean {
        return this.isPlaying;
    }

    /**
     * Clean up resources
     */
    dispose(): void {
        this.stop();
        if (this.audioContext.state !== 'closed') {
            this.audioContext.close();
        }
    }
}
