const c = (n) => `rgb(var(--${n}) / <alpha-value>)`

/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  darkMode: ['class', '[data-theme="dark"]'],
  theme: {
    extend: {
      colors: {
        bg: c('bg'),
        panel: c('panel'),
        raised: c('raised'),
        overlay: c('overlay'),
        hover: c('hover'),
        line: c('line'),
        line2: c('line2'),
        fg: c('fg'),
        fg2: c('fg2'),
        fg3: c('fg3'),
        accent: c('accent'),
        ok: c('ok'),
        warn: c('warn'),
        bad: c('bad'),
      },
      fontFamily: {
        sans: ['"Inter Variable"', 'Inter', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono Variable"', '"JetBrains Mono"', 'ui-monospace', 'monospace'],
      },
      fontSize: {
        '2xs': ['10.5px', '14px'],
        xs: ['11.5px', '16px'],
        sm: ['12.5px', '18px'],
        base: ['13px', '20px'],
      },
      keyframes: {
        shimmer: { '0%': { backgroundPosition: '-200% 0' }, '100%': { backgroundPosition: '200% 0' } },
        pulseDot: { '0%,100%': { opacity: 0.35 }, '50%': { opacity: 1 } },
        slide: { '0%': { transform: 'translateX(-100%)' }, '100%': { transform: 'translateX(250%)' } },
        fadeIn: { from: { opacity: 0, transform: 'translateY(3px)' }, to: { opacity: 1, transform: 'none' } },
      },
      animation: {
        shimmer: 'shimmer 1.6s linear infinite',
        pulseDot: 'pulseDot 1.2s ease-in-out infinite',
        slide: 'slide 1.4s ease-in-out infinite',
        fadeIn: 'fadeIn 140ms ease-out both',
      },
    },
  },
  plugins: [],
}
