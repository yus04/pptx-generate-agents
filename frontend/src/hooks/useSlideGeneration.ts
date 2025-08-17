import { useState, useEffect } from 'react';
import { useMsal } from '@azure/msal-react';
import apiService from '../services/apiService';
import { SlideGenerationJob } from '../types';

export const useSlideGeneration = () => {
  const [currentJob, setCurrentJob] = useState<SlideGenerationJob | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { accounts } = useMsal();

  useEffect(() => {
    // Set auth token when account changes
    if (accounts.length > 0) {
      const account = accounts[0];
      // In a real implementation, you would get the access token
      // For now, we'll store a placeholder
      localStorage.setItem('authToken', 'placeholder_token');
    }
  }, [accounts]);

  const generateSlides = async (request: any) => {
    try {
      setIsGenerating(true);
      setError(null);
      
      const response = await apiService.generateSlides(request);
      
      // Start polling for job status
      pollJobStatus(response.job_id);
      
      return response;
    } catch (error: any) {
      setError(error.message || 'スライド生成に失敗しました');
      setIsGenerating(false);
      throw error;
    }
  };

  const pollJobStatus = async (jobId: string) => {
    const pollInterval = setInterval(async () => {
      try {
        const job = await apiService.getJobStatus(jobId);
        setCurrentJob(job);
        
        if (job.status === 'completed' || job.status === 'failed') {
          clearInterval(pollInterval);
          setIsGenerating(false);
        }
      } catch (error) {
        clearInterval(pollInterval);
        setError('ジョブステータスの取得に失敗しました');
        setIsGenerating(false);
      }
    }, 2000);

    return () => clearInterval(pollInterval);
  };

  const approveAgenda = async (jobId: string, approved: boolean, agenda?: any) => {
    try {
      await apiService.approveAgenda(jobId, approved, agenda);
      
      if (approved) {
        // Continue polling for job status
        pollJobStatus(jobId);
      } else {
        setCurrentJob(null);
        setIsGenerating(false);
      }
    } catch (error: any) {
      setError(error.message || 'アジェンダ承認に失敗しました');
    }
  };

  return {
    currentJob,
    isGenerating,
    error,
    generateSlides,
    approveAgenda,
    setError,
  };
};