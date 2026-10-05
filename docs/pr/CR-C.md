Pieteikums: tracker/CR-C.md

<!-- PR piezīmes melnraksts pēc .github/pull_request_template.md. Atverot PR, saturu iekopēt PR aprakstā. -->

## 1. Pieteikums un kritēriji

**Ko izstrādājām:** jaunu galapunktu `POST /submissions/{id}/extend` pēc `docs/openapi.yaml` (`extendSubmission`, `ExtendRequest`). Līgums nav mainīts. `app/storage.py` ir mainīts tikai A1 labojuma dēļ (skat. zemāk un 4. sadaļu). Pēc pamatfunkcionalitātes pabeigšanas papildus pievienota darbinieka UI lapa `ui/statuss.html` (skat. „Papildu funkcionalitāte” zemāk).

| Izmaiņa | Vieta | Kritēriji un lēmumi |
|---|---|---|
| `ExtendRequest`: `newDueDate` tikai `YYYY-MM-DD` (`mode="before"` validators); `reason` apgriež un tad pārbauda garumu 10–500 (`StringConstraints(strip_whitespace=True, ...)`) | `app/models.py` | AC7, PO4, PO5, T1 |
| `InvalidState` → 409 `INVALID_STATE`, `InvalidDueDate` → 400 `INVALID_DUE_DATE`. Ziņojumi ir fiksēti, kā līguma piemēros, bez `details` un bez ievades | `app/errors.py` | AC3, AC4, AC5, AC9 |
| `add_months()`: +4 kalendāra mēneši. Ja mērķa mēnesī nav tāda datuma, ņem mēneša pēdējo dienu | `app/main.py` | AC2, AC3, PO1 |
| `extend_submission`: secība validācija → 404 → 409 → `INVALID_DUE_DATE` (pārbaudes ir `_ensure_extendable`) → nosacīta termiņa maiņa → audits `EXTEND` (apgriezts iemesls) → žurnālā tikai ID. Ja nosacītā maiņa neizdodas (konkurējošs pieprasījums), pārbaudes atkārto un atgriež precīzu kļūdu. Statuss nemainās; pārbaudes pret šodienas datumu nav | `app/main.py` | AC1–AC9, PO2, PO3, PO6, PO7, PO8, A1 |
| `extend_due_date`: termiņu maina viens nosacīts `UPDATE ... WHERE id = ? AND dueDate < ? AND status IN (...)` | `app/storage.py` | AC4, AC5 konkurences apstākļos (A1) |

Kritēriji AC1–AC9 ir izpildīti, un katram ir automātiskais tests (skat. 3. sadaļu).

**Pamatota atkāpe no sākotnējā plāna:** plāns paredzēja `app/storage.py` nemainīt. Pārskatīšanā atrastā A1 dēļ tajā pievienota funkcija `extend_due_date`. Atomāru nosacīto ierakstu nevar izveidot ar esošajām funkcijām: `update_due_date` raksta bez nosacījuma, bet `_lock` ir moduļa iekšējs, tāpēc `main.py` to nevar turēt visā pārbaudes un ieraksta laikā. Esošās `storage.py` funkcijas nav mainītas, arī `update_due_date` (B1 netiek skarts). `/extend` to vairs neizmanto.

**T1 īstenošana:** `Annotated[date, Strict()]` nederēja. FastAPI ķermeni validē Python režīmā, un strict režīmā tas noraida arī derīgo `"2026-12-15"`. Tas pārbaudīts pirms implementācijas. Tāpēc formātu pārbauda `mode="before"` validators ar `[0-9]{4}-[0-9]{2}-[0-9]{2}` (`[0-9]`, nevis `\d`, lai nepieņemtu Unicode ciparus). Neesošus datumus (`2026-02-30`) pēc tam noraida Pydantic. Visas formāta kļūdas esošais `_issue()` kartē uz `INVALID_FORMAT`.

**Papildu funkcionalitāte: darbinieka UI lapa `ui/statuss.html`.** Papildus API risinājumam izveidota darbinieka lapa termiņa pagarināšanas vizuālai izmantošanai un pārbaudei (`/ui/statuss.html`, arī `/ui/statuss.html?id=IES-2026-000006`). Šī ir papildu funkcionalitāte ārpus sākotnējā CR-C tvēruma: PO9 noteica, ka UI netiek veidots. Lapa pievienota pēc CR-C pamatfunkcionalitātes pabeigšanas un nomerģēšanas (PR #1), lai risinājumu varētu vizuāli demonstrēt. Lapā var:
- atvērt iesniegumu pēc numura (`GET /submissions/{id}`);
- redzēt statusu un aktuālo atbildes termiņu, kā arī tēmu un saņemšanas laiku (UTC). Personas datus lapa nerāda;
- ievadīt jauno termiņu un pagarināšanas iemeslu;
- izsaukt esošo `POST /submissions/{id}/extend`;
- redzēt saprotamus validācijas un kļūdu paziņojumus: lauka kļūdas no `VALIDATION_ERROR` `details`, `INVALID_DUE_DATE`, `INVALID_STATE`, `NOT_FOUND`. Pēc `INVALID_STATE` vai `INVALID_DUE_DATE` lapa ielādē aktuālos datus;
- pēc veiksmīgas pagarināšanas redzēt jauno termiņu un `EXTEND` ierakstu darbību vēsturē (`GET /submissions/{id}/audit`).

Lapa termiņa noteikumus pati nepārbauda: visus CR-C nosacījumus pārbauda API, un lapa tikai parāda API atbildi (CLAUDE.md: „Validāciju dari API. Forma tikai parāda API kļūdu”). API, līgums un testi šīs lapas dēļ nav mainīti.

**Neskaidrība:**

Pieteikumā atvērtais jautājums bija: kā skaitīt 4 mēnešus, ja mērķa mēnesī nav saņemšanas dienas datuma. Produkta īpašnieks atļāva izdarīt pamatotus pieņēmumus. 2026-10-05 fiksēti šie lēmumi:

| # | Jautājums | Lēmums |
|---|---|---|
| 1 | +4 mēneši, ja mērķa mēnesī nav tāda datuma (atvērtais jautājums CR-C.md) | Izmanto mērķa mēneša pēdējo dienu. Piemēri: 31.05.2026 + 4 mēn. = 30.09.2026; 31.10.2026 + 4 mēn. = 28.02.2027. Sākumpunkts ir `receivedAt` datums (UTC), kā noteikts CR-C precizējumos. |
| 2 | Vai `newDueDate` drīkst būt pagātnē? | Jā, ja tas ir vēlāks par pašreizējo `dueDate` un nepārsniedz +4 mēnešu robežu. Pārbaudes pret šodienas datumu nav. |
| 3 | Vai drīkst pagarināt jau nokavētu termiņu? | Jā, ja izpildās pārējie CR-C nosacījumi. |
| 4 | Iemesla atstarpes | `reason` vispirms apgriež (trim), un tikai pēc tam pārbauda garumu: 10–500 rakstzīmes. Iemesls tikai no atstarpēm nav derīgs. Ja pagarināšana izdodas, audita ieraksta `detail` laukā saglabā apgriezto vērtību. |
| 5 | Kļūdas kods iemeslam, kas īsāks par 10 rakstzīmēm | `VALIDATION_ERROR` ar `issue: INVALID_FORMAT` (šī vērtība līgumā jau ir atļauta). Līgumu ar `TOO_SHORT` nepaplašinām. |
| 6 | Kļūdu prioritāte | Vispirms tiek validēta pieprasījuma struktūra un formāts (400 `VALIDATION_ERROR`). Ja pieprasījums ir derīgs: nezināms ID → 404 `NOT_FOUND`; neatļauts statuss → 409 `INVALID_STATE`; neatļauts `newDueDate` → 400 `INVALID_DUE_DATE`. |
| 7 | Vai pagarināšana maina statusu? | Nē. |
| 8 | Audita ieraksts | `EXTEND`, kur `detail` ir tikai pagarināšanas iemesls, kā noteikts CR-C. |
| 9 | UI | Pogu formā neveidojam. Tvērums ir tikai API pēc pieteikuma un līguma. |
| 10 | Esošie defekti | Nesaistītus defektus šajā CR nelabojam. Ja kāds no tiem tieši traucē izpildīt CR-C vai AC9 ceļā `/extend`, to vispirms norāda. Pārējos atradumus pieraksta 4. sadaļā. |

**Tehniskās realizācijas un validācijas lēmumi** (tie nav jaunas produkta prasības, bet līguma un AC interpretācija ieviešanā):

| # | Lēmums | Pamatojums |
|---|---|---|
| T1 | `newDueDate` pieņem tikai formātā `YYYY-MM-DD`. Pydantic lax konvertēšanu neizmantojam, tāpēc citi pieraksti (piemēram, Unix laika zīmogs) tiek noraidīti ar 400 `VALIDATION_ERROR`. | Līgumā `newDueDate` ir `type: string, format: date`, un AC7 prasa noraidīt nepareizu datuma formātu. Pydantic `date` lax režīmā pēc noklusējuma pieņemtu arī citus pierakstus. |

## 2. MI lietošana

- **Galvenās uzvednes (1–3):**
  1. Plāna režīmā: „Sagatavo detalizētu ieviešanas plānu tracker/CR-C.md … Katram plānotajam risinājumam norādi, kuru prasību vai acceptance criterion tas izpilda … sasaisti katru CR-C acceptance criterion ar konkrētu testu … Beigās atsevišķi uzskaiti riskus … Neko nemaini.”
  2. „Sāc implementāciju atbilstoši apstiprinātajam plānam … uzturi docs/pr/CR-C.md … Ja atklājas būtiska neatbilstība starp plānu, tracker/CR-C.md, API contract vai docs/pr/CR-C.md, neizdomā jaunu risinājumu pats — apstājies.”
- **MI priekšlikums, ko noraidījāt vai labojāt, un kāpēc:**
  - Sākotnējais MI sabotāžas priekšlikums priekšlaicīgi paredzēja konkrētu koda konstrukciju (salīdzinājumu `<=` nomainīt uz `<`), kad implementācija vēl neeksistēja. Sabotāžu pārformulējām prasības līmenī: pēc implementācijas īslaicīgi panākt, ka precīza +4 mēnešu robeža (`newDueDate == limit`) tiek kļūdaini noraidīta, un pārbaudīt, ka vismaz `test_crc_ac2_exact_four_month_boundary_allowed` kļūst sarkans.

## 3. Pārbaude

- **Testi (nosaukumi):** `tests/test_crc_extend.py`. `make test`: 96 passed (no tiem 40 CR-C testa gadījumi kopā ar parametrizāciju, ieskaitot 2 A1 regresijas testus). Esošie testi paliek zaļi.

  | Kritērijs / lēmums | Tests |
  |---|---|
  | AC1 | `test_crc_ac1_extends_due_date[RECEIVED, IN_PROGRESS]` (arī PO7: statuss nemainās) |
  | AC2 | `test_crc_ac2_exact_four_month_boundary_allowed` |
  | AC3 | `test_crc_ac3_beyond_four_months_rejected` |
  | AC4 | `test_crc_ac4_not_later_than_current_rejected[vienāds, agrāks]` |
  | AC5 | `test_crc_ac5_invalid_state_rejected[FORWARDED, ANSWERED, WITHDRAWN]`, `test_crc_ac5_state_checked_before_date` (PO6) |
  | AC6 | `test_crc_ac6_unknown_id_404`, `test_crc_ac6_validation_before_not_found` (PO6) |
  | AC7 | `test_crc_ac7_validation_error` (13 gadījumi ar `field` un `issue`), `test_crc_ac7_reason_length_boundaries[10, 500]`, `test_crc_ac7_reason_trimmed_before_length_check` (PO4, PO5, T1) |
  | AC8 | `test_crc_ac8_audit_has_extend_with_reason` (PO4, PO8) |
  | AC9 | `test_crc_ac9_no_personal_data_in_logs_or_errors` |
  | PO1 | `test_crc_add_months` (5 gadījumi), `test_crc_month_end_clamped_via_api` |
  | PO2, PO3 | `test_crc_overdue_due_date_can_be_extended_into_past` |
  | Atkārtota pagarināšana (precizējums) | `test_crc_can_extend_multiple_times` |
  | A1 (pārskatīšanas atradums) | `test_crc_a1_concurrent_extend_cannot_shorten_due_date` (AC4), `test_crc_a1_concurrent_status_change_returns_409` (AC5) |

  Kļūdu gadījumu testi ar esošu iesniegumu pārbauda arī, ka `dueDate` nav mainījies un auditā nav `EXTEND`.
- **A1 regresijas testi:** konkurējošo darbību deterministiski iesprauž starp pārbaudes lasījumu (`storage.get`) un ierakstu (`monkeypatch`, bez pavedieniem un laika).
  - Pret kodu pirms labojuma: **2 failed**. Abos gadījumos `assert 200 == 400` / `assert 200 == 409`, jo konkurējošs pieprasījums tika apstiprināts.
  - Pēc labojuma: **2 passed**; `tests/test_crc_extend.py` 40 passed; `make test` 96 passed.
- **Sabotāža:** ko mainījāt (fails:rinda), kurš tests kļuva sarkans:
  - **Izmaiņa:** `app/main.py:196` (rindas numurs attiecas uz stāvokli pirms A1 labojuma; pēc labojuma šis nosacījums ir `_ensure_extendable` funkcijā), `if not current < data.newDueDate <= limit:` → `if not current < data.newDueDate < limit:`. Precīza +4 mēnešu robeža (`newDueDate == limit`) tika kļūdaini noraidīta.
  - **Rezultāts:** `pytest tests/test_crc_extend.py`: 2 failed, 36 passed (sabotāža veikta pirms A1 labojuma, kad CR-C testu bija 38).
    - `test_crc_ac2_exact_four_month_boundary_allowed`: `assert 400 == 200` (saņemts 2026-09-25, `newDueDate` 2027-01-25 noraidīts ar 400).
    - `test_crc_month_end_clamped_via_api`: `assert 400 == 200` (saņemts 2026-05-31, robeža 2026-09-30 noraidīta ar 400).
  - **Atjaunošana:** nosacījums atgriezts uz `<= limit`. `app/main.py` sakrīt baitu līmenī ar stāvokli pirms sabotāžas (sha256 un `cmp` pret kopiju). `make test`: 94 passed (pirms A1 regresijas testu pievienošanas).
- **Manuālā pārbaude `/docs`** (Swagger UI), iesniegums `IES-2026-000006`, `receivedAt` = `2026-09-25T13:40:00Z`, sākotnējais `dueDate` = `2026-10-26`. Secīgi veikti pieprasījumi:

  | # | `newDueDate` | Rezultāts | Kritērijs |
  |---|---|---|---|
  | 1 | `2026-10-29` | 200, atbildē `dueDate` = `2026-10-29` | AC1 |
  | 2 | `2026-10-28` (nav vēlāks par aktuālo termiņu `2026-10-29`) | 400 `INVALID_DUE_DATE` | AC4 |
  | 3 | `2027-01-25` (precīza +4 kalendāro mēnešu robeža) | 200, atbildē `dueDate` = `2027-01-25` | AC2 |
  | 4 | `2027-01-26` (viena diena aiz +4 mēnešu robežas) | 400 `INVALID_DUE_DATE` | AC3 |

- **Ekrānuzņēmums:** viena kritērija pieprasījums un atbilde `/docs`: AC2 robežgadījums, `POST /submissions/IES-2026-000006/extend` ar `newDueDate` = `2027-01-25` → 200, atbildē `dueDate` = `2027-01-25`. Ekrānuzņēmums saglabāts manuāli.
- **UI lapa `ui/statuss.html`:**
  - Pārbaudīts, ka serveris lapu pasniedz (200 `text/html`).
  - Ar tiem pašiem pieprasījumiem, ko sūta lapa, pret palaistu serveri pārbaudītas API atbildes, kuras lapa attēlo: tukša forma → `VALIDATION_ERROR` (`newDueDate`, `reason` → `REQUIRED`); īss iemesls → `reason` → `INVALID_FORMAT`; datums, kas vienāds ar pašreizējo termiņu, un 2027-01-26 → `INVALID_DUE_DATE`; 2027-01-25 → 200; `ANSWERED` → `INVALID_STATE`; nezināms numurs → `NOT_FOUND`.
  - Lapas JavaScript pārlūkā automātiski nav pārbaudīts, jo izstrādes vidē nav pārlūka. `make test`: 96 passed (UI testu nav).

## 4. Atradumi

**Pārskatīšana:** 2026-10-05, projekta subaģents `parskatitajs` pret `docs/review-checklist.md`. Tvērums: CR-C izmaiņas `app/models.py`, `app/errors.py`, `app/main.py`, `tests/test_crc_extend.py`, `docs/pr/CR-C.md` un `/extend` ceļā izmantotais apkārtējais kods. Bloķējošu atradumu nav. Rindu numuri atbilst darba kokam pirms A1 labojuma.

Kategorijas: **A** = CR-C izmaiņu radīts; **B** = jau iepriekš eksistējošs, uz `/extend` ceļa; **C** = ārpus CR-C tvēruma.

| # | Vieta (fails:rinda) | Nozīmīgums | Ietekme | Lēmums | Pamatojums |
|---|---|---|---|---|---|
| **A1** | `app/main.py:187-199`, `app/storage.py:249-260` | **jālabo** | Sacensību stāvoklis (TOCTOU). Statusu un `newDueDate` pārbauda pēc `storage.get` rezultāta, bet `storage.update_due_date` raksta bez nosacījuma. FastAPI sinhronos galapunktus izpilda pavedienu kopā, tāpēc divi vienlaicīgi pieprasījumi var abi izlasīt veco termiņu. Piemērs: `dueDate` 2026-10-26; pieprasījumi A (2026-12-15) un B (2026-11-01) abi saņem 200; ja B ieraksta pēc A, gala termiņš ir 2026-11-01. Termiņš tiek **saīsināts**, kas pārkāpj AC4 (`newDueDate` jābūt vēlākam par pašreizējo `dueDate`). Saīsināšana arī ir ārpus CR-C tvēruma. Auditā paliek divi `EXTEND` ieraksti. Tāds pats latents risks pastāv statusam: kad tiks ieviesti CR-A/CR-B, varēs pagarināt arī `WITHDRAWN`/`FORWARDED` iesniegumu (AC5). | **Labot** (šī PR galvenais atradums) | Atradumu radīja CR-C kods, un tas pārkāpj CR-C kritēriju. **Labots**, skat. zemāk. |
| A2 | `app/main.py:195`, `tests/test_crc_extend.py:25` | sīkums | UTC konvertācija `receivedAt` netiek testēta, jo visi testi lieto `+00:00`. Ja `.astimezone(timezone.utc)` izņemtu, testi to nepamanītu. Pārskatītājs pārbaudīja, ka kods ir pareizs. | Nelabot šajā CR | Uzvedība ir pareiza. Tas ir testu pārklājuma papildinājums, nevis defekts. |
| A3 | `app/models.py:104-106` | sīkums | `"   abc     "` (11 rakstzīmes) atbilst līguma `minLength: 10`, bet saņem 400, jo garumu pārbauda pēc apgriešanas. | Nelabot | Apzināts produkta īpašnieka lēmums PO4/PO5, dokumentēts 1. sadaļā. |
| A4 | `app/models.py:104`, `tests/test_crc_extend.py:150-154` | sīkums | Iemesls no nulles platuma atstarpēm (`\u200b`) tiek pieņemts, jo `strip` tās nenoņem. AC6 tests nepārbauda `message`. | Nelabot šajā CR | Plašāka apgriešana pārsniegtu PO4 noteikto. `message` ir fiksēta konstante, ko pārbauda AC3/AC5 testi. |
| A5 | `app/main.py:199-200` | sīkums | Termiņa maiņa un audita ieraksts nav vienā transakcijā. Ja `add_audit` neizdotos, termiņš būtu mainīts bez `EXTEND` ieraksta. | Nelabot šajā CR | Nav sasniedzams bez iekšējas SQLite kļūmes. A1 labojumam tas nav nepieciešams. |
| B1 | `app/errors.py:66-68`, `app/storage.py:256-259` | jālabo (atsevišķi) | Vispārējais apstrādātājs atgriež `str(exc)`. `LookupError` no `update_due_date` atklātu ID, SQLite versiju un `db=:memory:`. Dzēšanas lietotnē nav, tāpēc šis izņēmums praktiski nav sasniedzams. Pēc A1 labojuma `/extend` vairs neizsauc `update_due_date`; uz `/extend` ceļa paliek tikai vispārējā apstrādātāja `str(exc)` risks jebkuram negaidītam izņēmumam. | Atsevišķs labojums (PO10) | Jau iepriekš eksistējoša problēma uz `/extend` ceļa. Netraucē izpildīt CR-C. |
| C1 | `app/main.py:179-184` | sīkums | Ģenerētajā `/openapi.json` ir lieka 422 atbilde, reāli tiek atgriezts 400. Tas pats ir visos galapunktos. | Ārpus CR-C tvēruma | Patiesības avots ir `docs/openapi.yaml`, un uzvedība tam atbilst. |
| C2 | `app/main.py:185` | sīkums | Ceļa parametrs ģenerētajā shēmā ir `submission_id`, līgumā `id`. | Ārpus CR-C tvēruma | Esošais paraugs visos galapunktos. Uzvedību neietekmē. |
| C3 | `app/storage.py:267` | nopietns (CR-B) | SQL injekcija `find_institution` (f-string vaicājumā). | Ārpus CR-C tvēruma | `/extend` šo funkciju neizsauc. Jālabo kopā ar CR-B. |
| C4 | `requirements.txt` | — | `requests==2.31.0` ir ar zināmām ievainojamībām. `fastapi` versija nav fiksēta. Pydantic nav norādīts tieši. | Ārpus CR-C tvēruma | CR-C jaunas atkarības nepievieno. |

**A1 pierādījums:**

- **Problēma pirms labojuma:** iesniegums ar `dueDate` 2026-10-26. Pieprasījums B (`newDueDate` 2026-11-01) izlasa ierakstu. Pirms B ieraksta konkurējošs pieprasījums A pagarina termiņu līdz 2026-12-15. B tomēr saņem **200**, un gala `dueDate` ir **2026-11-01**: termiņš saīsināts, AC4 pārkāpts. Pārbaudīts atmiņā pret kodu pirms labojuma. Abi regresijas testi tad bija sarkani (`assert 200 == 400`, `assert 200 == 409`).
- **Labojums:**
  - `app/storage.py`: jauna funkcija `extend_due_date()`. Pārbaude un ieraksts ir viens nosacīts `UPDATE submissions SET dueDate = ? WHERE id = ? AND dueDate < ? AND status IN (?, ?)` zem `_lock`. Atgriež `None`, ja nosacījums neizpildījās. `dueDate` glabājas formātā `YYYY-MM-DD`, tāpēc virkņu salīdzinājums ir hronoloģisks.
  - `app/main.py`: esošās pārbaudes pārvietotas uz `_ensure_extendable()`, loģika un secība nav mainīta (PO6). `extend_submission` izsauc `storage.extend_due_date`. Ja tā atgriež `None`, pārbaudes atkārto pret aktuālo ierakstu un atgriež precīzu kļūdu (404/409/400 `INVALID_DUE_DATE`). Ja kļūdu nevar noteikt, atbilde ir 400 `INVALID_DUE_DATE` (fail-safe).
- **Regresijas testi:**
  - `test_crc_a1_concurrent_extend_cannot_shorten_due_date`: sagaida 400 `INVALID_DUE_DATE`, `dueDate` paliek 2026-12-15, B neieraksta `EXTEND`.
  - `test_crc_a1_concurrent_status_change_returns_409`: konkurējoša statusa maiņa uz `FORWARDED`, sagaida 409 `INVALID_STATE`, `dueDate` nemainās.
- **Pārbaude pēc labojuma:** A1 testi 2 passed; `tests/test_crc_extend.py` 40 passed; `make test` 96 passed; `ruff format --check` un `ruff check` bez piezīmēm.
- **`bandit` (`make check` daļa):** `app/storage.py:275` B608. Tas ir viltus pozitīvs rezultāts, jo f-string veido tikai `?` vietturus un vērtības tiek padotas kā parametri. Otrs B608 ir `app/storage.py:286` (`find_institution`), tas ir jau zināmais C3.
- **Netestēts atzars:** 404 pēc konkurējošas izmaiņas, jo lietotnē nav dzēšanas operācijas.

**Iepriekš identificētie kandidāti** (pirms pārskatīšanas, rindu numuri atbilst `main`, komits 7c5cf17):

| Vieta (fails:rinda) | Kontrolsaraksta punkts | Apraksts | Statuss pēc pārskatīšanas |
|---|---|---|---|
| `app/storage.py:256`, `app/errors.py:50` | 5 | `storage.update_due_date` met `LookupError` ar iekšēju tehnisko informāciju (SQLite versija, `db=:memory:`). Vispārējais apstrādātājs to atgriež kā 500 `INTERNAL_ERROR` ar `str(exc)`. | Apstiprināts kā **B1**. Atsevišķs labojums (PO10) |
| `app/models.py:82` | 2 | `Submission` modelī nav līgumā norādīto `ForwardInfo` lauku (`forwardedTo`, `forwardedAt`, `forwardedLate`). Līgumā tie nav obligāti, tāpēc `/extend` 200 atbilde līgumam atbilst. Tas attiecas uz CR-B. | Pārskatītājs apstiprināja, ka 200 atbilde atbilst līgumam. Ārpus CR-C tvēruma (CR-B) |
| `app/storage.py:245` | 4 | `storage.update_status` žurnālā raksta visu ierakstu, arī personas kodu, vārdu, e-pastu un iesnieguma tekstu. `/extend` šo funkciju neizmanto. | Pārskatītājs apstiprināja, ka `/extend` to neizsauc. Ārpus CR-C tvēruma |

## 5. Ierobežojumi

**Risinājuma ierobežojumi:**
- Pārskatīšanā konstatētais sacensību stāvoklis (A1: vienlaicīgi `/extend` pieprasījumi varēja termiņu saīsināt) ir **novērsts** ar nosacītu `UPDATE` (4. sadaļa). Atzars „404 pēc konkurējošas izmaiņas” nav testēts, jo lietotnē nav dzēšanas operācijas.
- **Zināms ierobežojums (A5):** termiņa maiņa un `EXTEND` audita ieraksts nav vienā transakcijā. Ja `add_audit` neizdotos, termiņš būtu mainīts bez audita ieraksta.
- Iemesla garumu skaita Unicode koda punktos (Python `len`, tāpat kā JSON Schema `minLength`/`maxLength`). Salikta zīme (burts + kombinējošā diakritiskā zīme) tiek skaitīta kā 2 rakstzīmes.
- Apgriešana (`strip_whitespace`) noņem visas Unicode atstarpes (arī `\n`, `\t`, NBSP). Šādi interpretējam PO4 „trim”.
- `newDueDate: null` un `reason: null` dod `issue: INVALID_FORMAT`, nevis `REQUIRED` (AC7 prasa tikai `VALIDATION_ERROR`).
- Lieki lauki pieprasījumā tiek ignorēti (Pydantic noklusējums, tāpat kā citos galapunktos). Līgumā `additionalProperties` nav norādīts.
- 200 atbildē nav `ForwardInfo` lauku (CR-B kandidāts 4. sadaļā). Līgumā tie nav obligāti.
- Nezināms ID kopā ar nederīgu ķermeni dod 400, nevis 404 (PO6).

**Apzināti ārpus CR-C tvēruma:** UI poga vai forma (PO9). Pēc pamatfunkcionalitātes demonstrēšanai papildus pievienota darbinieka lapa `ui/statuss.html` (1. sadaļa), bet `darbinieks.html` sarakstā saites uz to nav, un automātisku UI testu nav. Tāpat ārpus tvēruma: paziņojums iedzīvotājam; termiņa saīsināšana; darba dienu pārbaude; laika joslas (tikai UTC); `docs/openapi.yaml` izmaiņas (piem., `TOO_SHORT`); 4. sadaļā minēto esošo kandidātu labošana (PO10). Juridiskās nodaļas komentārs par saprotamu iemeslu ir informācija darbiniekam. Iemesla satura pārbaude nav ieviesta.
