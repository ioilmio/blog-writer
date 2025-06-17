// import { useEffect, useState } from 'react';
// import type { Article } from './types/Article';

// interface PipelineJob {
//   job_id: string;
//   status: string;
//   current_step?: string;
//   generate?: { status: string; result: any; error?: string };
//   image?: { status: string; result: any; error?: string };
//   upsert?: { status: string; result: any; error?: string };
// }

// export default function PipelineDashboard() {
//   const [jobs, setJobs] = useState<PipelineJob[]>([]);
//   const [selectedJob, setSelectedJob] = useState<PipelineJob | null>(null);
//   const [loading, setLoading] = useState(false);

//   // Poll jobs (for demo, fetch all jobs from backend JSON file)
//   useEffect(() => {
//     const fetchJobs = async () => {
//       setLoading(true);
//       try {
//         const res = await fetch('/api/pipeline/jobs'); // You may need to add this endpoint or serve the JSON file
//         if (res.ok) {
//           const data = await res.json();
//           setJobs(Object.entries(data).map(([job_id, job]) => ({ job_id, ...job })));
//         }
//       } catch (e) {
//         // ignore
//       } finally {
//         setLoading(false);
//       }
//     };
//     fetchJobs();
//     const interval = setInterval(fetchJobs, 3000);
//     return () => clearInterval(interval);
//   }, []);

//   const handleApprove = async (job: PipelineJob, step: string) => {
//     const result = job[step]?.result;
//     await fetch(`/api/pipeline/approve/${job.job_id}/${step}`, {
//       method: 'POST',
//       headers: { 'Content-Type': 'application/json' },
//       body: JSON.stringify({ result }),
//     });
//   };

//   const handleRetry = async (job: PipelineJob, step: string) => {
//     await fetch(`/api/pipeline/retry/${job.job_id}/${step}`, { method: 'POST' });
//   };

//   return (
//     <div className="bg-white p-6 rounded-lg shadow-md mt-8">
//       <h2 className="text-xl font-bold mb-4">Pipeline Jobs</h2>
//       {loading && <div>Loading jobs...</div>}
//       <table className="w-full text-sm mb-4">
//         <thead>
//           <tr>
//             <th className="text-left">Job ID</th>
//             <th>Status</th>
//             <th>Step</th>
//             <th>Actions</th>
//           </tr>
//         </thead>
//         <tbody>
//           {jobs.map(job => (
//             <tr key={job.job_id} className="border-b">
//               <td>{job.job_id}</td>
//               <td>{job.status}</td>
//               <td>{job.current_step}</td>
//               <td>
//                 {['generate', 'image', 'upsert'].map(step =>
//                   job[step]?.status === 'waiting_approval' ? (
//                     <button
//                       key={step}
//                       className="bg-blue-500 text-white px-2 py-1 rounded mr-2"
//                       onClick={() => handleApprove(job, step)}
//                     >
//                       Approve {step}
//                     </button>
//                   ) : job[step]?.status === 'error' ? (
//                     <button
//                       key={step}
//                       className="bg-red-500 text-white px-2 py-1 rounded mr-2"
//                       onClick={() => handleRetry(job, step)}
//                     >
//                       Retry {step}
//                     </button>
//                   ) : null
//                 )}
//                 <button
//                   className="bg-gray-200 px-2 py-1 rounded"
//                   onClick={() => setSelectedJob(job)}
//                 >
//                   Details
//                 </button>
//               </td>
//             </tr>
//           ))}
//         </tbody>
//       </table>
//       {selectedJob && (
//         <div className="border p-4 rounded bg-gray-50">
//           <h3 className="font-semibold mb-2">Job Details: {selectedJob.job_id}</h3>
//           <pre className="text-xs overflow-x-auto bg-gray-100 p-2 rounded">
//             {JSON.stringify(selectedJob, null, 2)}
//           </pre>
//           <button className="mt-2 text-blue-600 underline" onClick={() => setSelectedJob(null)}>
//             Close
//           </button>
//         </div>
//       )}
//     </div>
//   );
// }
