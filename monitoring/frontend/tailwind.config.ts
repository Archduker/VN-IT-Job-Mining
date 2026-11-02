import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './index.html',
    './src/**/*.{ts,tsx}',
  ],
  darkMode: 'class',
  theme: {
    extend: {
      fontFamily: {
        sans: ['"Be Vietnam Pro"', 'system-ui', 'sans-serif'],
        mono: ['"Be Vietnam Pro"', 'system-ui', 'sans-serif'],
      },
      colors: {
        brand: {
          50: '#EFEDFD',
          100: '#E7E4FC',
          500: '#5B4CE6',
          600: '#4B3FD1',
          700: '#3D3399',
          900: '#2E2580',
        },
        ground: '#F4F4F7',
        panel: '#F7F7FA',
        line: { DEFAULT: '#ECEBF2', strong: '#E2E1EA' },
        ink: { DEFAULT: '#1C1B26', soft: '#3A3850', muted: '#5D5B6E', faint: '#6B6980' },
        nav: { DEFAULT: '#1C1B26', active: '#34304A', text: '#C9C6DA' },
        state: {
          'done-bg': '#DDF1E6', 'done-fg': '#17643F',
          'partial-bg': '#FFF0D6', 'partial-fg': '#8A5300',
          'fail-bg': '#FBE3E1', 'fail-fg': '#9E241E',
          'running-bg': '#E7E4FC', 'running-fg': '#3D3399',
          'idle-bg': '#EAE9F0', 'idle-fg': '#4E4C5E',
        },
        // Các trang cũ viết theo nền tối: đảo dải slate để chúng hiển thị trên nền sáng.
        emerald: { 200: '#17643F', 300: '#17643F', 400: '#17643F', 900: '#DDF1E6', 950: '#DDF1E6' },
        rose: { 200: '#9E241E', 300: '#9E241E', 400: '#9E241E', 900: '#FBE3E1', 950: '#FBE3E1' },
        amber: { 200: '#8A5300', 300: '#8A5300', 400: '#8A5300', 900: '#FFF0D6', 950: '#FFF0D6' },
        indigo: { 200: '#3D3399', 300: '#3D3399', 400: '#3D3399', 900: '#EFEDFD', 950: '#EFEDFD' },
        violet: { 200: '#3D3399', 300: '#3D3399', 400: '#3D3399', 900: '#EFEDFD', 950: '#EFEDFD' },
        purple: { 200: '#3D3399', 300: '#3D3399', 400: '#3D3399', 900: '#EFEDFD', 950: '#EFEDFD' },
        cyan: { 200: '#0E6470', 300: '#0E6470', 400: '#0E6470', 900: '#DCF3F5', 950: '#DCF3F5' },
        blue: { 200: '#1F4FA0', 300: '#1F4FA0', 400: '#1F4FA0', 900: '#E3ECFB', 950: '#E3ECFB' },
        slate: {
          50: '#1C1B26', 100: '#1C1B26', 200: '#2A2838', 300: '#3A3850', 400: '#5D5B6E',
          500: '#6B6980', 600: '#A9A6BD', 700: '#E2E1EA', 800: '#ECEBF2', 900: '#FFFFFF', 950: '#F4F4F7',
        },
      },
    },
  },
  plugins: [],
}

export default config
