'use client';

import { useCallback, useEffect, useState, useRef } from 'react';
import { Play, Pause, Square, Mic } from 'lucide-react';
import { SummaryResponse } from '@/types/summary';

interface RecordingControlsProps {
  isRecording: boolean;
  barHeights: string[];
  onRecordingStop: () => void;
  onRecordingStart: () => void;
  onTranscriptReceived: (summary: SummaryResponse) => void;
}

export const RecordingControls: React.FC<RecordingControlsProps> = ({
  isRecording,
  barHeights,
  onRecordingStop,
  onRecordingStart,
  onTranscriptReceived,
}) => {
  const [showPlayback, setShowPlayback] = useState(false);
  const [recordingPath, setRecordingPath] = useState<string | null>(null); // Will store Blob URL
  const [transcript, setTranscript] = useState<string>('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [isStarting, setIsStarting] = useState(false);
  const [isStopping, setIsStopping] = useState(false);
  const [stopCountdown, setStopCountdown] = useState(5);
  const countdownInterval = useRef<NodeJS.Timeout | null>(null);
  const stopTimeoutRef = useRef<{ stop: () => void } | null>(null);
  
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);


  const currentTime = 0;
  const duration = 0;
  const isPlaying = false;
  const progress = 0;

  const formatTime = (time: number) => {
    const minutes = Math.floor(time / 60);
    const seconds = Math.floor(time % 60);
    return `${minutes}:${seconds.toString().padStart(2, '0')}`;
  };

  // Tauri-specific useEffect removed.

  const handleStartRecording = useCallback(async () => {
    if (isStarting || isRecording) return;
    console.log('Starting recording (Web API)...');
    setIsStarting(true);
    setShowPlayback(false);
    setTranscript('');
    audioChunksRef.current = []; // Clear previous chunks

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      mediaRecorderRef.current = new MediaRecorder(stream);

      mediaRecorderRef.current.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorderRef.current.onstop = async () => {
        console.log('MediaRecorder stopped.');
        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
        const audioUrl = URL.createObjectURL(audioBlob);
        setRecordingPath(audioUrl);
        // setShowPlayback(true); // You might want to enable playback UI here

        // TODO: Send audioBlob to backend for transcription
        // For now, we'll just log it and call onRecordingStop
        console.log('Recorded audio Blob:', audioBlob);
        console.log('Blob URL:', audioUrl);
        
        // Simulate processing for now
        setIsProcessing(true);
        // Replace with actual API call to backend
        // const formData = new FormData();
        // formData.append('audio_file', audioBlob, 'recording.webm');
        // try {
        //   const response = await fetch('/api/transcribe', { // Replace with your actual API endpoint
        //     method: 'POST',
        //     body: formData,
        //   });
        //   if (!response.ok) throw new Error('Transcription failed');
        //   const summary: SummaryResponse = await response.json();
        //   onTranscriptReceived(summary);
        // } catch (transcriptionError) {
        //   console.error('Transcription error:', transcriptionError);
        //   alert('Failed to get transcript. Please check console.');
        // } finally {
        //   setIsProcessing(false);
        // }
        
        // For now, just stop processing and call onRecordingStop
        setTimeout(() => { // Simulate delay
            setIsProcessing(false);
            onRecordingStop();
        }, 1000);


        // Clean up the stream
        if (streamRef.current) {
            streamRef.current.getTracks().forEach(track => track.stop());
            streamRef.current = null;
        }
      };

      mediaRecorderRef.current.start();
      console.log('MediaRecorder started successfully.');
      setIsProcessing(false); // No initial processing for start
      onRecordingStart();
    } catch (error) {
      console.error('Failed to start recording (Web API):', error);
      alert('Failed to start recording. Please ensure microphone access is granted and check the console for details.');
      // Clean up the stream if it was partially started
        if (streamRef.current) {
            streamRef.current.getTracks().forEach(track => track.stop());
            streamRef.current = null;
        }
    } finally {
      setIsStarting(false);
    }
  }, [onRecordingStart, onTranscriptReceived, isRecording, isStarting]);

  const stopRecordingAction = useCallback(async () => {
    console.log('Executing stop recording (Web API)...');
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
      mediaRecorderRef.current.stop(); // This will trigger the onstop event
    } else {
      console.warn('MediaRecorder not recording or not initialized.');
      // If not recording, ensure UI reflects this
      onRecordingStop();
    }
    // setIsProcessing(true) is handled in onstop or if needed here
    // onRecordingStop() is called in onstop or if stop is called when not recording
    setIsStopping(false); // Reset stopping flag
  }, [onRecordingStop]);
  
  // useEffect for cleanup
  useEffect(() => {
    return () => {
      if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
        mediaRecorderRef.current.stop();
      }
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(track => track.stop());
      }
      if (countdownInterval.current) {
        clearInterval(countdownInterval.current);
      }
    };
  }, []);


  const handleStopRecording = useCallback(async () => {
    if (!isRecording || isStarting || isStopping ) return;
    
    console.log('Starting stop countdown...');
    setIsStopping(true);
    setStopCountdown(5);

    // Clear any existing intervals
    if (countdownInterval.current) {
      clearInterval(countdownInterval.current);
      countdownInterval.current = null;
    }

    // Create a controller for the stop action
    const controller = {
      stop: () => {
        if (countdownInterval.current) {
          clearInterval(countdownInterval.current);
          countdownInterval.current = null;
        }
        setIsStopping(false);
        setStopCountdown(5);
      }
    };
    stopTimeoutRef.current = controller;

    // Start countdown
    countdownInterval.current = setInterval(() => {
      setStopCountdown(prev => {
        if (prev <= 1) {
          // Clear interval first
          if (countdownInterval.current) {
            clearInterval(countdownInterval.current);
            countdownInterval.current = null;
          }
          // Schedule stop action
          stopRecordingAction();
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
  }, [isRecording, isStarting, isStopping, stopRecordingAction]);

  const cancelStopRecording = useCallback(() => {
    if (stopTimeoutRef.current) {
      stopTimeoutRef.current.stop();
      stopTimeoutRef.current = null;
    }
  }, []);

  useEffect(() => {
    return () => {
      if (countdownInterval.current) clearInterval(countdownInterval.current);
      if (stopTimeoutRef.current) stopTimeoutRef.current.stop();
    };
  }, []);

  return (
    <div className="flex flex-col space-y-2">
      <div className="flex items-center space-x-2 bg-white rounded-full shadow-lg px-4 py-2">
        {isProcessing ? (
          <div className="flex items-center space-x-2">
            <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-gray-900"></div>
            <span className="text-sm text-gray-600">Processing recording...</span>
          </div>
        ) : (
          <>
            {showPlayback ? (
              <>
                <button
                  onClick={handleStartRecording}
                  className="w-10 h-10 flex items-center justify-center bg-red-500 rounded-full text-white hover:bg-red-600 transition-colors"
                >
                  <Mic size={16} />
                </button>

                <div className="w-px h-6 bg-gray-200 mx-1" />

                <div className="flex items-center space-x-1 mx-2">
                  <div className="text-sm text-gray-600 min-w-[40px]">
                    {formatTime(currentTime)}
                  </div>
                  <div 
                    className="relative w-24 h-1 bg-gray-200 rounded-full"
                  >
                    <div 
                      className="absolute h-full bg-blue-500 rounded-full" 
                      style={{ width: `${progress}%` }}
                    />
                  </div>
                  <div className="text-sm text-gray-600 min-w-[40px]">
                    {formatTime(duration)}
                  </div>
                </div>

                <button 
                  className="w-10 h-10 flex items-center justify-center bg-gray-300 rounded-full text-white cursor-not-allowed"
                  disabled
                >
                  <Play size={16} />
                </button>
              </>
            ) : (
              <>
                <button
                  onClick={isRecording ? 
                    (isStopping ? cancelStopRecording : handleStopRecording) : 
                    handleStartRecording}
                  disabled={isStarting || isProcessing}
                  className={`w-12 h-12 flex items-center justify-center ${
                    isStarting || isProcessing ? 'bg-gray-400' : 'bg-red-500 hover:bg-red-600'
                  } rounded-full text-white transition-colors relative`}
                >
                  {isRecording ? (
                    <>
                      <Square size={20} />
                      {isStopping && (
                        <div className="absolute -top-8 text-red-500 font-medium">
                          {stopCountdown > 0 ? `${stopCountdown}s` : 'Stopping...'}
                        </div>
                      )}
                    </>
                  ) : (
                    <Mic size={20} />
                  )}
                </button>

                <div className="flex items-center space-x-1 mx-4">
                  {barHeights.map((height, index) => (
                    <div
                      key={index}
                      className="w-1 bg-red-500 rounded-full transition-all duration-200"
                      style={{
                        height: isRecording ? height : '4px',
                      }}
                    />
                  ))}
                </div>
              </>
            )}
          </>
        )}
      </div>
      {/* {showPlayback && recordingPath && (
        <div className="text-sm text-gray-600 px-4">
          Recording saved to: {recordingPath}
        </div>
      )} */}
    </div>
  );
};