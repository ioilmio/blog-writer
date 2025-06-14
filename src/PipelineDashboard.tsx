import { useEffect, useState } from 'react';

interface StepResult {
  status: string;
  result: unknown;
  error?: string;
}

interface PipelineJob {
  job_id: string;
  status: string;
  current_step?: string;
  generate?: StepResult;
  image?: StepResult;
  upsert?: StepResult;
}

const stepKeys = ['generate', 'image', 'upsert'] as const;
type StepKey = typeof stepKeys[number];

type JobsApiResponse = Record<string, Omit<PipelineJob, 'job_id'>>;

export default function PipelineDashboard() {
  const [jobs, setJobs] = useState<PipelineJob[]>([]);
  const [selectedJob, setSelectedJob] = useState<PipelineJob | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Poll jobs (fetch all jobs from backend JSON file or API endpoint)
  useEffect(() => {
    const fetchJobs = async () => {
      setLoading(true);
      setError(null);
      try {
        let res = await fetch('/api/pipeline/jobs');
        if (!res.ok) {
          // fallback: try to fetch the JSON file directly
          res = await fetch('/pipeline_jobs.json');
        }
        if (res.ok) {
          const data: JobsApiResponse = await res.json();
          // Ensure all required fields are present
          const mapped: PipelineJob[] = Object.entries(data).map(([job_id, job]) => ({
            job_id,
            status: job.status || 'unknown',
            current_step: job.current_step,
            generate: job.generate,
            image: job.image,
            upsert: job.upsert,
          }));
          setJobs(mapped);
        } else {
          setError('Could not fetch pipeline jobs.');
        }
      } finally {
        setLoading(false);
      }
    };
    fetchJobs();
    const interval = setInterval(fetchJobs, 3000);
    return () => clearInterval(interval);
  }, []);

  const getStepData = (job: PipelineJob, step: StepKey): StepResult | undefined => {
    return job[step];
  };

  const handleApprove = async (job: PipelineJob, step: StepKey) => {
    const stepData = getStepData(job, step);
    if (!stepData) return;
    const result = stepData.result;
    try {
      await fetch(`/api/pipeline/approve/${job.job_id}/${step}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ result }),
      });
    } catch {
      setError('Failed to approve step.');
    }
  };

  const handleRetry = async (job: PipelineJob, step: StepKey) => {
    try {
      await fetch(`/api/pipeline/retry/${job.job_id}/${step}`, { method: 'POST' });
    } catch {
      setError('Failed to retry step.');
    }
  };

  return (
    <div className="bg-white p-6 rounded-lg shadow-md mt-8">
      <h2 className="text-xl font-bold mb-4">Pipeline Jobs</h2>
      {loading && <div>Loading jobs...</div>}
      {error && <div className="text-red-500 mb-2">{error}</div>}
      <table className="w-full text-sm mb-4">
        <thead>
          <tr>
            <th className="text-left">Job ID</th>
            <th>Status</th>
            <th>Step</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {jobs.map(job => (
            <tr key={job.job_id} className="border-b">
              <td>{job.job_id}</td>
              <td>{job.status}</td>
              <td>{job.current_step}</td>
              <td>
                {stepKeys.map(step => {
                  const stepData = getStepData(job, step);
                  if (stepData?.status === 'waiting_approval') {
                    return (
                      <button
                        key={step}
                        className="bg-blue-500 text-white px-2 py-1 rounded mr-2"
                        onClick={() => handleApprove(job, step)}
                      >
                        Approve {step}
                      </button>
                    );
                  } else if (stepData?.status === 'error') {
                    return (
                      <button
                        key={step}
                        className="bg-red-500 text-white px-2 py-1 rounded mr-2"
                        onClick={() => handleRetry(job, step)}
                      >
                        Retry {step}
                      </button>
                    );
                  }
                  return null;
                })}
                <button
                  className="bg-gray-200 px-2 py-1 rounded"
                  onClick={() => setSelectedJob(job)}
                >
                  Details
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {selectedJob && (
        <div className="border p-4 rounded bg-gray-50">
          <h3 className="font-semibold mb-2">Job Details: {selectedJob.job_id}</h3>
          <pre className="text-xs overflow-x-auto bg-gray-100 p-2 rounded">
            {JSON.stringify(selectedJob, null, 2)}
          </pre>
          <button className="mt-2 text-blue-600 underline" onClick={() => setSelectedJob(null)}>
            Close
          </button>
        </div>
      )}
    </div>
  );
}
