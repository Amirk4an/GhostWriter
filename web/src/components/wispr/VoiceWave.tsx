import { motion } from 'framer-motion'

const BAR_COUNT = 5
const BAR_WIDTH = 2
const BAR_MAX_H = 14

type VoiceWaveProps = {
  className?: string
  /** Slightly softer bars in command mode */
  variant?: 'listening' | 'command'
}

export function VoiceWave({ className = '', variant = 'listening' }: VoiceWaveProps) {
  const opacity = variant === 'command' ? 'bg-amber-200/60' : 'bg-sky-300/80'

  return (
    <div
      className={`flex h-5 items-end justify-center gap-px ${className}`}
      aria-hidden
    >
      {Array.from({ length: BAR_COUNT }, (_, i) => (
        <motion.div
          key={i}
          className={`rounded-full ${opacity}`}
          style={{
            width: BAR_WIDTH,
            height: BAR_MAX_H,
            transformOrigin: '50% 100%',
          }}
          animate={{ scaleY: [0.35, 1, 0.35] }}
          transition={{
            duration: 0.55,
            repeat: Infinity,
            delay: i * 0.09,
            ease: 'easeInOut',
          }}
        />
      ))}
    </div>
  )
}
