# ADR 0007: Asset And Environment Topology Boundary

## Status

Accepted

## Context

OpsPilot needs an operable resource topology that binds projects to DEV/QA/QE environments, members, assets, endpoints, and file attachments. The foundation service already owns projects, assets, environments, files, and audit events, so topology relationships should remain in this backend boundary instead of being reconstructed in the web console or in memory-only client state.

## Decision

Assets are global inventory records with category, status, capabilities, tags, properties, file references, and an optional parent asset. The parent relationship is a directed assembly edge and must reject self-references and indirect cycles.

Projects own the set of assets that can be used by their environments. An environment can bind only members already present in its project and assets already bound to its project. Cross-project environment asset/member references are rejected.

Files remain owned by the file-service boundary. Assets and environments store only `file_ids`; storage keys and capability URLs never appear in topology records. Environment file binding requires a project member actor who also owns the file. The binding accepts files already scoped to the same environment, atomically claims unbound files by setting their resource reference to the environment, and rejects files scoped to any other resource. Deleting a file removes its topology references, and deleting, retiring, archiving, or deletion-marking an asset removes project/environment asset references.

## Consequences

Frontend and API clients can query topology through filtered asset/environment lists and explicit nested bind/unbind routes. Clients must bind an asset to a project before assigning it to any environment in that project.

MySQL persistence continues to snapshot the store-facing aggregates and normalized relationship rows. The HTTP layer depends only on store methods and does not know about storage keys or database implementation details.
