// Copyright 2025-2026 Arun Rajkumar
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

// The Garden for someone outside the engineering workspace: the world and
// its people, without the code map. The code map (repositories, BUDs,
// bugs, features) is engineering data the server only gives engineers, so
// a board user's garden starts from this instead of asking for it. The org
// id is what joins the org's room, where everyone's characters and the
// board activity come from.

import type { TreeData } from '@/types/dashboard'

export function worldWithoutCode(orgId: string): TreeData {
  return {
    org_id: orgId,
    symbol_count: 0,
    relationship_count: 0,
    total_files: 0,
    total_lines: 0,
    project_age_days: 0,
    repos: [],
    branches: [],
    bud_stages: { bud: 0, design: 0, development: 0, testing: 0, uat: 0, prod: 0, closed: 0, discarded: 0 },
    total_features: 0,
    features: [],
    buds: [],
    members: [],
    threats: [],
    agent_activity: [],
    relationships: [],
    feature_skills: [],
  }
}
