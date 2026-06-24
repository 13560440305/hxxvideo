export default function VideoPlayer({ src, title }: { src: string; title?: string }) {
  return (
    <div className="bg-black rounded-lg overflow-hidden shadow-lg">
      <video
        controls
        className="w-full max-h-[500px]"
        title={title}
      >
        <source src={src} type="video/mp4" />
        Your browser does not support the video tag.
      </video>
    </div>
  );
}
