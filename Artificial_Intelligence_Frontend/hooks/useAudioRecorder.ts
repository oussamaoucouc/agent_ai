
import { useState, useRef, useCallback } from 'react';

export const useAudioRecorder = () => {
    const [isRecording, setIsRecording] = useState<boolean>(false);
    const mediaRecorderRef = useRef<MediaRecorder | null>(null);
    const audioChunksRef = useRef<Blob[]>([]);

    const startRecording = useCallback(async () => {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            const options: MediaRecorderOptions = { mimeType: 'audio/webm' };
            try {
                mediaRecorderRef.current = new MediaRecorder(stream, options);
            } catch {
                mediaRecorderRef.current = new MediaRecorder(stream);
            }
            audioChunksRef.current = [];

            mediaRecorderRef.current.ondataavailable = (event) => {
                audioChunksRef.current.push(event.data);
            };
            
            mediaRecorderRef.current.start();
            setIsRecording(true);
        } catch (error) {
            console.error("Error accessing microphone:", error);
            alert("Could not access microphone. Please check permissions.");
        }
    }, []);

    const stopRecording = useCallback((): Promise<Blob | null> => {
        return new Promise((resolve) => {
            if (mediaRecorderRef.current && isRecording) {
                mediaRecorderRef.current.onstop = () => {
                    const blob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
                    // Stop all media tracks to turn off the microphone light
                    mediaRecorderRef.current?.stream.getTracks().forEach(track => track.stop());
                    setIsRecording(false);
                    resolve(blob);
                };
                mediaRecorderRef.current.stop();
            } else {
                resolve(null);
            }
        });
    }, [isRecording]);

    return { isRecording, startRecording, stopRecording };
};
