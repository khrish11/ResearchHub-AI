# Founder And Owner Checklist

## What You Need To Do From Your Side

This is the non-coding work required to make the roadmap succeed.

## 1. Product Decisions

Decide the exact v1 scope:

1. Which citation styles must ship first
2. Whether AI Checker is only for uploaded PDFs or also workspace papers
3. Whether checker output is advisory only or part of writing workflows
4. Whether AI-writing likelihood detection is part of v1 or phase 2
5. Whether Q1/Q2 labels are mandatory for launch or phase 2

If these decisions stay fuzzy, implementation will drift.

## 2. Legal And Data Access Decisions

You need to decide what kind of paper access you want:

1. metadata only
2. open-access full text
3. licensed publisher full text

If you want strong Q-tier and publisher-grade coverage, you will need:

1. approved API accounts
2. license review
3. budget for commercial data access

## 3. Accounts And Vendor Setup

You should create and manage:

1. OpenAlex access plan if rate needs grow
2. Crossref contact and usage compliance setup
3. Europe PMC and OA source usage review
4. Elsevier developer account if you want Scopus-grade metadata
5. Springer Nature developer account if you want their APIs
6. GPU provider account if you want self-hosted inference
7. Hugging Face account for model storage and experiment tracking

## 4. Ground Truth And Evaluation

You need to help define what "good" means.

Prepare:

1. 50 to 100 papers for citation testing
2. 50 to 100 uploaded papers for checker evaluation
3. examples of good and bad checker outputs
4. examples of partial metadata edge cases
5. known human-written passages
6. known AI-assisted passages
7. ambiguous mixed passages for calibration

Without a benchmark, model quality arguments will be subjective.

## 5. Training Data Strategy

If you want your own trained model, you need to approve:

1. which data is allowed for training
2. whether user uploads can ever be used
3. whether opt-in consent is needed
4. what license flags must be stored

You should also decide whether the first custom model is for:

1. AI Checker only
2. longform writing only
3. AI-writing likelihood classification only
4. both

Start with one narrow target.

## 6. Budget Planning

You need a budget decision for:

1. API subscriptions
2. higher-rate metadata providers
3. GPU inference hosting
4. training experiments
5. observability and storage growth

If budget is tight, prioritize:

1. citations
2. AI Checker
3. OA access
4. later custom-model work

## 7. Policy And Compliance

Before using your own model in production, make sure you decide:

1. whether prompts are stored
2. whether uploads are stored long-term
3. whether outputs are used for model improvement
4. whether users need explicit consent
5. whether enterprise or academic customers need stricter data guarantees

You may need updates to:

1. privacy policy
2. terms of service
3. admin policy for internal analytics and model routing

## 8. Team And Workflow

If you are working with others, assign ownership:

1. product decisions
2. licensing and vendor communication
3. AI evaluation
4. frontend polish
5. backend provider integration
6. deployment and monitoring

If you are working alone, block time separately for:

1. product
2. engineering
3. vendor setup
4. evaluation

## 9. Launch Preparation

Before public launch of these features, make sure you have:

1. 1-line explanation of Citations
2. 1-line explanation of AI Checker
3. screenshots or demo flow
4. AI-writing disclaimer language
5. clear limitations messaging
6. support process for wrong citations, weak analysis, or false AI-writing flags

## 10. Recommended Order For You

From your side, do this in order:

1. Freeze feature scope for v1
2. Decide allowed paper sources and licensing boundaries
3. Decide whether Q-tier data is phase 1 or phase 2
4. Approve benchmark dataset creation, including human versus AI-assisted passage labels
5. Approve whether custom-model work starts now or later
6. Allocate budget for APIs and GPU if needed
7. Update policy language before any training-data use

## What I Recommend You Do Right Now

This week, you should do these concrete tasks:

1. Write the exact v1 definition of Citations in one paragraph
2. Write the exact v1 definition of AI Checker in one paragraph
3. Decide whether AI-writing likelihood detection is required in v1
4. Decide whether you want Q-tier data at launch or later
5. Decide whether you want only OA full text or paid publisher access too
6. Decide whether your own model is a phase-2 goal instead of immediate scope

The most practical answer for now is:

1. ship citations
2. ship AI Checker
3. strengthen metadata and OA coverage
4. then move to your own model after benchmarks and legal boundaries are clear
