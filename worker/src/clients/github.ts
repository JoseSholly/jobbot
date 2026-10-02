/** Triggers GitHub Actions workflows (needs a PAT with Actions: read & write). */
export class GitHubClient {
  constructor(
    private readonly token: string,
    private readonly repo: string,
    private readonly ref = "main",
    private readonly fetchFn: typeof fetch = fetch,
  ) {}

  async dispatch(workflowFile: string, inputs: Record<string, string>): Promise<void> {
    // Call fetch detached from `this`: Workers throw "Illegal invocation" otherwise.
    const doFetch = this.fetchFn;
    const res = await doFetch(
      `https://api.github.com/repos/${this.repo}/actions/workflows/${workflowFile}/dispatches`,
      {
        method: "POST",
        headers: {
          authorization: `Bearer ${this.token}`,
          accept: "application/vnd.github+json",
          "x-github-api-version": "2022-11-28",
          "user-agent": "jobbot-worker",
          "content-type": "application/json",
        },
        body: JSON.stringify({ ref: this.ref, inputs }),
      },
    );
    if (res.status !== 204) {
      throw new Error(`github dispatch ${res.status}: ${(await res.text()).slice(0, 200)}`);
    }
  }
}
