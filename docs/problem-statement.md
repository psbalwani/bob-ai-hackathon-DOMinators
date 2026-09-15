# Problem Statement

## Background

Pharma & Biotech — Problem Statement **P1: Clinical Trial Risk Monitor & Protocol Deviation Detector** (Critical Now). A single Phase III clinical trial can span **5,000+ patient visits across 200+ sites**. Every visit must follow a protocol spec that defines the visit schedule, dosing rules, and allowed/banned co-medications — but today, deviations from that spec are only discovered when an FDA auditor goes looking for them.

## The Problem

Protocol deviations — missed or late visits, dosing outside the approved range, banned co-medications administered anyway, required procedures skipped — currently go undetected until audit time, long after they happen. There is no system that continuously compares actual patient visit records against the protocol spec, grades the severity of what it finds, and tells a risk manager which sites are actually dangerous versus which just look busy.

## Who is Affected

- **Clinical Risk Manager** — needs a ranked, continuously updated view of which sites are highest-risk and *why*, not a static quarterly report.
- **Clinical Research Associate (CRA)** — needs to know exactly which visits/patients at their assigned sites currently have open deviations.
- **Regulatory/QA Lead** — needs CAPA (Corrective and Preventive Action) documentation that is audit-ready and traceable to the exact protocol clause violated.
- **Site Coordinator** — needs an early warning before a minor issue compounds into a major finding.

## Why It Matters

One rejected submission caused by an undetected protocol deviation can delay drug approval by **6–12 months** and cost **$50–100M**. Today, root-cause investigation into a deviation is a manual, multi-week process across scattered records — this system aims to bring that down to seconds, and to catch deviations in real time instead of at audit time.

## Why Existing Solutions Fall Short

Deviation review today is largely manual and retrospective: CRAs and QA leads reconcile visit records against the protocol by hand, usually triggered by a scheduled monitoring visit or an audit, not continuously. Existing EDC/CTMS systems (e.g., Medidata Rave, Veeva) capture the data but don't score site-level risk from leading indicators or automatically draft CAPA reports grounded in the specific protocol clause and ICH E6(R2) GCP severity definitions — so risk managers are left doing that synthesis themselves, after the fact, without a trustworthy, explainable risk score to prioritize where to look first.
