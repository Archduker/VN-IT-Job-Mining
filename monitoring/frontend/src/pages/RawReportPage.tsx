import React, { useState } from 'react'
import { api } from '../api/client'
import { FeatureTargets } from '../components/raw/FeatureTargets'
import { IssuesTable } from '../components/raw/IssuesTable'
import { RawSampleViewer } from '../components/raw/RawSampleViewer'
import { SourceOverview } from '../components/raw/SourceOverview'
import { SourcePicker } from '../components/raw/SourcePicker'
import { UnivariatePanel } from '../components/raw/UnivariatePanel'
import { ErrorState, LoadingState, useAsync } from '../components/ui'

export const RawReportPage: React.FC = () => {
  const [source, setSource] = useState<string>('careerviet')
  const overview = useAsync(() => api.sources(), [])
  const report = useAsync(() => api.report(source), [source])

  return (
    <div className="flex flex-col gap-6">
      <SourcePicker items={overview.data ?? []} selected={source} onSelect={setSource} />
      {report.error && <ErrorState />}
      {report.loading && !report.data && <LoadingState />}
      {report.data && (
        <>
          <SourceOverview report={report.data} />
          <FeatureTargets source={source} targets={report.data.targets} />
          <IssuesTable source={source} issues={report.data.issues} />
        </>
      )}
      <UnivariatePanel source={source} />
      <RawSampleViewer source={source} onSourceChange={setSource} />
    </div>
  )
}
