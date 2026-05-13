# AdFramework — Attribution Chain (Technical Detail)

> How a delivery row from MediaSmart gets attributed to a client in gold.
> Source: actual view DDL from `marts.io_delivery_daily_v4` and `stg.mediasmart_daily`.

```mermaid
flowchart TD
    A["raw.mediasmart_daily\nrow: controlid='123', eventid='ACC_LKB', strategyid='S1'\ndate='2026-03-15', impressions=10000"]

    B["stg.mediasmart_daily\nplatform_campaign_id = NULLIF(controlid, '') → '123'\nevent_id = NULLIF(eventid, '') → 'ACC_LKB'\nstrategy_id = NULLIF(strategyid, '') → 'S1'"]

    C["share.newad_operational_daily\nplatform = 'mediasmart'\nadvertiser_platform_id = CAST(event_id) → 'ACC_LKB'\nplatform_campaign_id = '123'\ndate = '2026-03-15'\nimpressions = 10000"]

    D["core.io_binding_registry_v4\nbinding_id = 'BND_01'\nplatform_campaign_id = '123'\nnewad_client_id = 'nwd_luckbet_a485d6bc'\nbinding_scope = 'campaign'\nstart_date = '2026-03-01', end_date = '2026-03-31'"]

    E["core.platform_client_links\nnewad_client_id = 'nwd_luckbet_a485d6bc'\nplatform = 'mediasmart'\nlink_value = 'ACC_LKB'"]

    F["links CTE\nLOWER(TRIM(link_value)) = 'acc_lkb'\nadvertiser_platform_id = 'acc_lkb'"]

    G{"INNER JOIN check\nd.platform_campaign_id = b.platform_campaign_id?\n'123' = '123' ✓\nd.date BETWEEN start AND end?\n'2026-03-15' BETWEEN '2026-03-01' AND '2026-03-31' ✓"}

    H{"LEFT JOIN check (optional)\nd.advertiser_platform_id = l.advertiser_platform_id?\n'ACC_LKB' = 'acc_lkb' ✗ case mismatch!\n⚠ BUT: OR d.advertiser_platform_id IS NULL\n→ passes silently if delivery has no eventid"}

    I["marts.io_delivery_daily_v4\nRow attributed:\nnewad_client_id = 'nwd_luckbet_a485d6bc'\nplatform_campaign_id = '123'\nimpressions = 10000"]

    J["marts.io_calc_daily_v4\nJOIN with io_schedule_daily_v4\n+ planned budget/volume added"]

    K["share.io_calc_daily_v4\nSELECT * — passthrough view"]

    L["gold.fct_delivery_daily\nFILTER: binding_scope = 'campaign'\nFILTER: platform_campaign_id IS NOT NULL\nFILTER: newad_client_id != 'nwd_luckbet_69e72f18'\nROW_NUMBER dedup by date+campaign+client"]

    MISS1["❌ NO BINDING EXISTS\nIf platform_campaign_id '123' has no row\nin io_binding_registry_v4\n→ delivery row dropped at INNER JOIN\n→ 0 impressions in gold for this campaign"]

    MISS2["⚠ CASE MISMATCH\ndelivery.advertiser_platform_id = 'ACC_LKB'\nlinks.advertiser_platform_id = 'acc_lkb'\nResult: advertiser_platform_id check fails\nBUT the OR IS NULL clause means the row\nstill passes — just without advertiser validation"]

    A -->|"same-day batch ingest"| B
    B -->|"aggregated by date+campaign+strategy\nCAST(event_id AS STRING)"| C

    E -->|"LOWER(TRIM(link_value))"| F

    C -->|"delivery CTE\nGROUP BY date, platform, campaign, strategy"| G
    D -->|"bindings CTE"| G

    G -->|"match ✓"| H
    F -->|"links CTE"| H

    H -->|"passes (optional join)"| I

    G -->|"no match → row dropped"| MISS1
    H -.->|"case mismatch noted"| MISS2

    I --> J
    J --> K
    K --> L

    style MISS1 fill:#ff4444,color:#fff,stroke:#cc0000
    style MISS2 fill:#ff8800,color:#fff
    style A fill:#e8f4fd
    style B fill:#e8f5e9
    style C fill:#e8f5e9
    style D fill:#f3e5f5
    style E fill:#f3e5f5
    style F fill:#f3e5f5
    style G fill:#fff9c4
    style H fill:#fff9c4
    style I fill:#fce4ec
    style J fill:#fce4ec
    style K fill:#fce4ec
    style L fill:#fff176
```

## Key observations from the actual DDL

| Step | What the code does | Risk |
|---|---|---|
| `stg.mediasmart_daily` | `NULLIF(controlid, '')` — empty strings become NULL | NULL campaign_id is filtered out downstream |
| `share.newad_operational_daily` | `CAST(event_id AS STRING)` — no LOWER, no TRIM | Case-sensitive advertiser_platform_id |
| `links CTE` in `io_delivery_daily_v4` | `LOWER(TRIM(link_value))` — normalizes the link | But delivery side is NOT lowercased — mismatch |
| `joined` CTE | `d.advertiser_platform_id = l.advertiser_platform_id OR d.advertiser_platform_id IS NULL` | If eventid is blank (NULL), the OR IS NULL lets the row through without advertiser validation |
| `stg.io_lines_v4` | `ROW_NUMBER PARTITION BY newad_client_id, proposal_month, platform_campaign_id ORDER BY io_id DESC` | If two IOs share same campaign_id in same month, only the latest survives — older is silently dropped |
| `gold.fct_delivery_daily` | `ROW_NUMBER PARTITION BY date, platform_campaign_id, newad_client_id ORDER BY proposal_month DESC` | One more dedup layer — campaign+date+client combination must be unique |
