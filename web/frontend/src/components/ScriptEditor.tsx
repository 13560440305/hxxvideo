import type { Scene } from '@/lib/api';

interface ScriptEditorProps {
  title: string;
  description: string;
  scenes: Scene[];
  onChange: (scenes: Scene[]) => void;
}

export default function ScriptEditor({ title, description, scenes, onChange }: ScriptEditorProps) {
  const updateScene = (index: number, field: keyof Scene, value: any) => {
    const updated = scenes.map((s, i) => (i === index ? { ...s, [field]: value } : s));
    onChange(updated);
  };

  return (
    <div className="space-y-4">
      <div className="bg-white rounded-lg border p-4">
        <h2 className="font-bold text-lg mb-1">{title}</h2>
        <p className="text-sm text-gray-500">{description}</p>
      </div>
      {scenes.map((scene, i) => (
        <div key={i} className="bg-white rounded-lg border border-gray-200 p-4 space-y-3">
          <h3 className="font-medium text-sm text-indigo-600">Scene {i + 1}</h3>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-gray-400 mb-0.5">Duration (s)</label>
              <input type="number" value={scene.duration}
                onChange={e => updateScene(i, 'duration', +e.target.value)}
                className="w-full border rounded px-2 py-1 text-sm" />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-0.5">Shot Type</label>
              <select value={scene.shot_type} onChange={e => updateScene(i, 'shot_type', e.target.value)}
                className="w-full border rounded px-2 py-1 text-sm">
                {['wide', 'medium', 'close', 'aerial', 'tracking', 'POV'].map(t =>
                  <option key={t} value={t}>{t}</option>)}
              </select>
            </div>
          </div>
          <div>
            <label className="block text-xs text-gray-400 mb-0.5">English Narration</label>
            <textarea value={scene.en_narration} rows={2}
              onChange={e => updateScene(i, 'en_narration', e.target.value)}
              className="w-full border rounded px-2 py-1 text-sm" />
          </div>
          <div>
            <label className="block text-xs text-gray-400 mb-0.5">中文解说</label>
            <textarea value={scene.zh_narration} rows={2}
              onChange={e => updateScene(i, 'zh_narration', e.target.value)}
              className="w-full border rounded px-2 py-1 text-sm" />
          </div>
          <div>
            <label className="block text-xs text-gray-400 mb-0.5">Visual Prompt</label>
            <textarea value={scene.visual_prompt} rows={1}
              onChange={e => updateScene(i, 'visual_prompt', e.target.value)}
              className="w-full border rounded px-2 py-1 text-sm" />
          </div>
        </div>
      ))}
    </div>
  );
}
