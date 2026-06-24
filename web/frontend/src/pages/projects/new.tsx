import { useEffect, useState } from 'react';
import { useRouter } from 'next/router';
import { api, Niche } from '@/lib/api';

export default function NewProject() {
  const router = useRouter();
  const [niches, setNiches] = useState<Niche[]>([]);
  const [topic, setTopic] = useState('');
  const [niche, setNiche] = useState('china_food');
  const [duration, setDuration] = useState(60);
  const [format, setFormat] = useState('youtube');
  const [skipVideo, setSkipVideo] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.listNiches().then(d => setNiches(d.niches)).catch(() => {});
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!topic.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const res = await api.createProject({
        topic: topic.trim(),
        niche,
        duration,
        fmt: format,
        skip_video: skipVideo,
      });
      router.push(`/projects/${res.project_id}`);
    } catch (err: any) {
      setError(err.message);
      setLoading(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold mb-6">New Project</h1>
      <form onSubmit={handleSubmit} className="space-y-5 bg-white rounded-lg border p-6">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Topic</label>
          <textarea value={topic} onChange={e => setTopic(e.target.value)}
            placeholder="e.g. 成都火锅的百年历史"
            className="w-full border rounded-lg px-3 py-2 text-sm" rows={2} required />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Niche</label>
            <select value={niche} onChange={e => setNiche(e.target.value)}
              className="w-full border rounded-lg px-3 py-2 text-sm">
              {niches.map(n => <option key={n.name} value={n.name}>{n.name}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Duration (s)</label>
            <input type="number" value={duration} onChange={e => setDuration(+e.target.value)}
              min={10} max={600} className="w-full border rounded-lg px-3 py-2 text-sm" />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Format</label>
            <select value={format} onChange={e => setFormat(e.target.value)}
              className="w-full border rounded-lg px-3 py-2 text-sm">
              <option value="youtube">YouTube (16:9)</option>
              <option value="shorts">Shorts (9:16)</option>
            </select>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <input type="checkbox" id="skipVideo" checked={skipVideo}
            onChange={e => setSkipVideo(e.target.checked)}
            className="rounded" />
          <label htmlFor="skipVideo" className="text-sm text-gray-600">Draft mode (skip video generation)</label>
        </div>

        {error && <p className="text-red-500 text-sm">{error}</p>}

        <button type="submit" disabled={loading || !topic.trim()}
          className="w-full bg-indigo-600 text-white py-2 rounded-lg font-medium hover:bg-indigo-700 disabled:opacity-50 transition-colors">
          {loading ? 'Creating...' : 'Create & Start Pipeline'}
        </button>
      </form>
    </div>
  );
}
