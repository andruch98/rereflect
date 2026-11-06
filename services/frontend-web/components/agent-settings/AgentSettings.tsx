'use client';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useAuth } from '@/contexts/AuthContext';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
import { agentSettingsAPI, type CommunitySettings, type ReviewSettings, type SurveySettings } from '@/lib/api/agent-settings';
import { ReviewSamples, reviewSteps } from './ReviewSteps';
import { surveySteps } from './SurveySteps';
import { SettingsFlow } from './SettingsFlow';

export function AgentSettings() {
  const { user } = useAuth();
  const client = useQueryClient();
  const queryKey = ['agent-settings', user?.organization_id, user?.id];
  const { data, isPending, isError, refetch } = useQuery({
    queryKey, queryFn: agentSettingsAPI.get, enabled: !!user, retry: false, refetchOnWindowFocus: false,
  });
  async function refresh() {
    await refetch({ throwOnError: true });
  }
  async function save<T extends ReviewSettings | SurveySettings>(name: 'reviews' | 'surveys', version: number, values: T) {
    const saved = await agentSettingsAPI.save(name, version, values);
    client.setQueryData<CommunitySettings>(queryKey, previous => previous && { ...previous, [name]: saved });
    const affected = name === 'surveys' ? ['surveys', 'survey'] : ['boomsay-review-reply'];
    for (const resource of affected) {
      void client.invalidateQueries({ queryKey: [resource, user?.organization_id, user?.id] });
    }
  }
  return <div className="mx-auto w-full max-w-4xl space-y-5 px-4 py-6 sm:px-6">
    <h1 className="text-3xl font-semibold">Agent Settings</h1>
    {isPending && <p role="status">Loading community settings…</p>}
    {isError && <div role="alert" className="space-y-2"><p>Could not load this community’s settings.</p>
      <Button variant="outline" onClick={() => void refetch()}>Try again</Button></div>}
    {data && <Tabs key={`${user?.organization_id}-${user?.id}-${data.can_edit}`} defaultValue="reviews">
      <TabsList aria-label="Agent settings sections" className="mb-3">
        <TabsTrigger value="reviews">Review Responses</TabsTrigger><TabsTrigger value="surveys">Surveys</TabsTrigger>
      </TabsList>
      <TabsContent value="reviews" forceMount className="data-[state=inactive]:hidden">
        <SettingsFlow section={data.reviews} canEdit={data.can_edit} steps={reviewSteps}
          onSave={(version, values) => save('reviews', version, values)} onRefresh={refresh}
          preview={(values, onReady) => <ReviewSamples values={values} onReady={onReady} />} />
      </TabsContent>
      <TabsContent value="surveys" forceMount className="data-[state=inactive]:hidden">
        <p className="mb-4 text-sm text-muted-foreground">Scheduled invitations and reminders are simulated in this preview. Residents receive no email from this schedule.</p>
        <SettingsFlow section={data.surveys} canEdit={data.can_edit} steps={surveySteps}
          onSave={(version, values) => save('surveys', version, values)} onRefresh={refresh} />
      </TabsContent>
    </Tabs>}
  </div>;
}
