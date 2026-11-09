import { AlertCircle } from 'lucide-react'

import type { useCrawlingState } from './useCrawlingState'
type Props = Pick<ReturnType<typeof useCrawlingState>, 'syncFeedback' | 'setSyncFeedback' | 'errorMessage' | 'setErrorMessage'>
export function CrawlingFeedback({ syncFeedback, setSyncFeedback, errorMessage, setErrorMessage }: Props) {
 return <>
      {/* Feedback banners */}
      {syncFeedback && (
        <div className="p-3.5 rounded-xl bg-indigo-500/10 border border-indigo-500/20 text-indigo-300 text-xs flex items-center justify-between">
          <span>{syncFeedback}</span>
          <button onClick={() => setSyncFeedback(null)} className="text-ink-soft hover:text-ink">✕</button>
        </div>
      )}
      {errorMessage && (
        <div className="p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
            <span>{errorMessage}</span>
          </div>
          <button onClick={() => setErrorMessage(null)} className="text-ink-soft hover:text-ink ml-2">✕</button>
        </div>
      )}


 </>
}
