/**
 * Fullscreen background — renders a looping <video> for .webm/.mp4
 * or an <img> for static formats. Fixed position, behind all content.
 */
const VIDEO_EXTS = new Set(['.webm', '.mp4', '.mov', '.avi'])

function ext(filename) {
  const i = filename.lastIndexOf('.')
  return i >= 0 ? filename.slice(i).toLowerCase() : ''
}

const BASE_STYLE = {
  position:      'fixed',
  inset:         0,
  width:         '100%',
  height:        '100%',
  objectFit:     'cover',
  zIndex:        0,
  pointerEvents: 'none',
}

export default function Background({ filename }) {
  if (!filename) return null

  const src     = `/api/backgrounds/${encodeURIComponent(filename)}`
  const isVideo = VIDEO_EXTS.has(ext(filename))

  if (isVideo) {
    return (
      <video
        key={src}
        src={src}
        autoPlay
        muted
        loop
        playsInline
        style={BASE_STYLE}
        aria-hidden="true"
      />
    )
  }

  return (
    <img
      key={src}
      src={src}
      alt=""
      style={BASE_STYLE}
      aria-hidden="true"
    />
  )
}
