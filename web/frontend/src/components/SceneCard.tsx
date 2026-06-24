import type { Scene } from '@/lib/api';

export default function SceneCard({ scene, index }: { scene: Scene; index: number }) {
  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4">
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-bold text-indigo-600">Scene {index + 1}</span>
        <span className="text-xs text-gray-400">{scene.duration}s &middot; {scene.shot_type}</span>
      </div>
      <div className="text-sm space-y-2">
        <div>
          <span className="text-xs text-gray-400 font-medium">EN</span>
          <p className="text-gray-800">{scene.en_narration}</p>
        </div>
        <div>
          <span className="text-xs text-gray-400 font-medium">ZH</span>
          <p className="text-gray-600">{scene.zh_narration}</p>
        </div>
        <div>
          <span className="text-xs text-gray-400 font-medium">Visual Prompt</span>
          <p className="text-gray-500 text-xs">{scene.visual_prompt}</p>
        </div>
      </div>
    </div>
  );
}
