import { useCrawlingState } from '../components/crawling/useCrawlingState'
import { CrawlingHeader } from '../components/crawling/CrawlingHeader'
import { LakehouseHealthCard } from '../components/crawling/LakehouseHealthCard'
import { CrawlingFeedback } from '../components/crawling/CrawlingFeedback'
import { CrawlingSchedule } from '../components/crawling/CrawlingSchedule'
import { SourceSelector } from '../components/crawling/SourceSelector'
import { LedgerMetrics } from '../components/crawling/LedgerMetrics'
import { CrawlTriggerCard } from '../components/crawling/CrawlTriggerCard'
import { RealtimeLogStream } from '../components/crawling/RealtimeLogStream'
import { LedgerStatusTable } from '../components/crawling/LedgerStatusTable'
export function CrawlingPage() {
 const state = useCrawlingState()
 return <div className="space-y-6 min-w-0">
  <CrawlingHeader {...state} />
  <LakehouseHealthCard {...state} />
  <CrawlingFeedback {...state} />
  <CrawlingSchedule {...state} />
  <SourceSelector {...state} />
  <LedgerMetrics {...state} />
  <CrawlTriggerCard {...state} />
  <RealtimeLogStream {...state} />
  <LedgerStatusTable {...state} />
</div>
}
export default CrawlingPage
