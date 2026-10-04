# 01 — Problem Statement

A visually impaired person may know a kitchen only through touch, memory, or assistance from another person. Existing vision demos often detect isolated objects, but they do not learn the user's actual kitchen layout as persistent memory.

This MVP addresses a narrower hackathon question:

> Can a kitchen be taught to an AI system from one narrated walkthrough video, stored as a spatial-semantic memory, and used to guide a safe simplified tea-preparation task?

The project is not trying to certify a navigation aid. It is a controlled local demonstration of environmental learning, memory, querying, and audio guidance.

## User need

The system should help the user understand where relevant objects are in a familiar kitchen and provide simple spoken guidance during a constrained task.

## Technical gap

Object detection alone is insufficient. The important system capability is persistent environment memory:

- where objects were observed,
- which zones they belong to,
- how they relate to one another,
- which facts came from visual evidence,
- which facts were confirmed by narration,
- and which facts remain uncertain.

## MVP success statement

The demo succeeds when the system can process a real narrated kitchen walkthrough video, build a Kitchen Knowledge Graph, query it during a simplified tea workflow, and speak guidance through the laptop speaker.
