import * as fs from 'fs';
import * as path from 'path';
import { Credentials } from '../auth';

export interface ResolvedCaseInput {
  caseFile: Record<string, unknown>;
  hypothesis: string;
  resolution: string;
}

export function writeResolvedCase(input: ResolvedCaseInput, creds: Credentials): string {
  const dir = path.resolve(process.cwd(), creds.wikiCasesDir);
  fs.mkdirSync(dir, { recursive: true });

  const ts = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
  const filepath = path.join(dir, `case-${ts}.md`);

  const identity = input.caseFile['identity'] as Record<string, unknown> | undefined;
  const subject = identity?.['email'] ?? identity?.['auth0Id'] ?? 'unknown';

  const content = `---
type: case
product: harmony-auth
resolvedAt: ${new Date().toISOString()}
subject: ${subject}
---

# Case: ${input.hypothesis}

## Hypothesis

${input.hypothesis}

## Resolution

${input.resolution}

## Evidence

\`\`\`json
${JSON.stringify(input.caseFile, null, 2)}
\`\`\`
`;

  fs.writeFileSync(filepath, content, 'utf-8');
  return filepath;
}
