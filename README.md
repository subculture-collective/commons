# Commons

![Commons identity](docs/brand/commons/readme-lockup.png)

Commons is a community hub for people rebuilding familiar tools in the open.
You can discover open projects, compare software alternatives, find work to
help build, and coordinate through progress updates and threaded discussions.

It runs at <https://commons.subcult.tv/>. The site starts without invented
accounts or activity; the project catalog is seeded with curated references to
existing open-source software.

## Features

- **Project discovery**: search, categories, status filters, sorting and
  featured projects.
- **Replacement index** (`/alternatives`, with pages such as
  `/alternatives/photoshop`): familiar tools with workflow-specific comparisons,
  filters for maturity, platform, hosting, license scope and coverage, and
  sources with review dates. Products with no reviewed alternative link to
  `/start/<product>`, where you can add an existing project or follow a starter
  guide.
- **Build guide** (`/guides/build-an-alternative`): setup and investigation,
  behavior specifications, an editable project brief, implementation,
  verification and inviting collaborators.
- **Active rebuilds** (`/build`): projects in progress and links to upstream
  contribution opportunities.
- **Accounts**: password login, a private recovery key shown once at
  registration, password changes and account deletion. Optional verified email
  enables password reset.
- **Builder profiles**: skills, websites, owned projects and profile editing.
- **Repository claims**: listings start unclaimed. A maintainer claims one by
  committing a proof file to the repository on GitHub or git.subcult.tv, then
  manages its links, contribution needs and progress updates. Member projects
  can list up to five products they help replace.
- **Collaboration**: private bookmarks, memberships with contribution roles,
  progress updates and discussions with replies.
- **Activity feed**: paginated, filterable by everyone or your projects, linking
  to the exact update or conversation.
- **Moderation**: member reports, content hiding, discussion removal, report
  resolution and account suspension.
- **Server-rendered public pages** with canonical URLs and metadata for search
  engines.

Data is stored in SQLite on the server. No default accounts or passwords are
shipped, and there are no analytics or advertising integrations. Curated
references do not imply affiliation with their maintainers.

## Quick start

Requires Node.js 24 or newer.

```sh
git clone https://github.com/subculture-collective/commons.git
cd commons
npm ci
npm run dev:server
```

In a second terminal:

```sh
npm run dev
```

Open <http://localhost:5173>. The API runs on port 3001 and Vite proxies `/api`
to it. Register an account, save the recovery key, then make it an
administrator:

```sh
npm run admin -- promote your-username
```

The catalog lives in `server/catalog.js` and is imported on startup.
`npm run admin -- import-catalog` runs the same import by hand.

### Checks

```sh
npm test               # API, database and tool tests with isolated databases
npm run format:check   # Prettier
npm run check:seo      # build and check the server-rendered pages
npm run build          # production frontend and server-render bundles
npm audit --omit=dev
```

## Configuration

Copy `.env.example` to `.env`.

| Variable | Purpose |
| --- | --- |
| `PUBLIC_URL` | Public HTTPS origin, no path or trailing slash (required in production) |
| `OPERATOR_NAME` | Public operator identity (required in production) |
| `CONTACT_EMAIL` | Monitored contact address (required in production) |
| `APP_PORT` | Host port for the Compose service (default 3000) |
| `IMAGE_TAG` | Image tag for Compose |
| `TRUST_PROXY` | Set to `1` only behind exactly one trusted HTTPS reverse proxy |
| `BACKUP_DIR` | Host directory for database backups |
| `DATABASE_PATH` | SQLite file path when running Node directly |
| `BREVO_API_KEY`, `BREVO_SENDER_EMAIL`, `BREVO_SENDER_NAME` | Optional transactional email through Brevo; an empty key turns email off |

Keep the email API key in the private production `.env` only.

## Deploy

The Dockerfile builds the frontend and server-render bundles and runs the app
as an unprivileged user on port 3000 with a health check. `compose.yaml` runs
one replica with a persistent SQLite volume, a read-only root filesystem and a
backup mount:

```sh
cp .env.example .env   # fill in the production values
docker compose up -d --build
```

Put it behind an HTTPS reverse proxy and set up off-host backups with
`npm run backup` and `npm run restore` before accepting users.
[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) covers configuration, backups,
restore, updates and rollback. [docs/API.md](docs/API.md) describes the API.

## Project layout

| Path | Contents |
| --- | --- |
| `src/` | React frontend and server-render entry |
| `server/` | Express API, SQLite access, catalog, mail queue and tests |
| `shared/` | Code used by both sides (SEO metadata) |
| `scripts/` | Backup, restore, health check and SEO check |
| `public/`, `assets/` | Icons, social image and brand files |

## Contributing

- Bugs and feature requests: [GitHub issues](https://github.com/subculture-collective/commons/issues).
- Questions and ideas: [GitHub Discussions](https://github.com/subculture-collective/commons/discussions).
- Code: open a pull request on GitHub against `main`.

CI runs the Prettier check, tests, the SEO check, `npm audit` and a production
image build on every pull request.

## License

Code is released under the [MIT License](LICENSE). The Commons mark, wordmark
and social image are CC BY 4.0, and the bundled fonts are under the SIL Open
Font License. See [docs/BRAND.md](docs/BRAND.md) for the full table.
