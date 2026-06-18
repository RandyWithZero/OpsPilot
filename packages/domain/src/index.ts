export type ActorRole = "Admin" | "Operator" | "Viewer";

export interface ActorContext {
  actorId: string;
  role: ActorRole;
  projectIds: readonly string[];
}

export const canManageProject = (actor: ActorContext, projectId: string): boolean => {
  if (actor.role === "Admin") {
    return true;
  }

  return actor.role === "Operator" && actor.projectIds.includes(projectId);
};
