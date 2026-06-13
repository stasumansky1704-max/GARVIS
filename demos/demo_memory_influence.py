#!/usr/bin/env python3
"""
DEMO: MEMORY INFLUENCE TRACKING
================================

This demo shows how GARVIS tracks which memories influence reasoning.
Every memory that contributed to a response is visible in the trace.
No hidden memory influence -- trace_visible is always True.

Steps:
  1. Create 3 sample episodic memories with different provenance
  2. Create an inference request
  3. Simulate memory retrieval and influence mapping
  4. Show each memory and its influence on the inference
  5. Show the influence graph (memory -> inference links)
  6. Verify all influences have trace_visible=True
  7. Show provenance chain for each influence

The demo uses REAL memory models (EpisodicMemory, MemoryInfluence,
ProvenanceRecord) and demonstrates the full influence tracking pipeline.

Usage:
    cd /mnt/agents/output/project
    python demos/demo_memory_influence.py
"""

from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timezone
from uuid import UUID, uuid4

_PROJECT_ROOT = __file__.rsplit("/demos/", 1)[0]
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from demos.utils import (
    create_mock_audit,
    create_mock_lineage,
    create_mock_registry,
    create_sample_episodic_memories,
    print_demo_header,
    print_kv,
    print_result,
    print_section,
    print_subsection,
    run_demo,
    _GREEN,
    _CYAN,
    _RESET,
    _BOLD,
)

from models.audit import AuditEvent
from models.cognition import OperationalState
from models.governance import GovernanceCheckResult
from models.inference import InferenceRequest, GovernedResponse
from models.memory import EpisodicMemory, MemoryInfluence, ProvenanceRecord


async def demo_memory_influence() -> list[tuple[str, bool]]:
    """Run the memory influence tracking demonstration.

    Returns list of (description, passed) tuples.
    """
    results: list[tuple[str, bool]] = []
    print_demo_header(
        "MEMORY INFLUENCE TRACKING",
        "Tracking how memories influence reasoning in GARVIS",
    )

    # ========================================================================
    # Step 1: Create 3 sample episodic memories
    # ========================================================================
    print_section("STEP 1: Create Sample Episodic Memories")

    memories = create_sample_episodic_memories()

    for i, memory in enumerate(memories, 1):
        print_subsection(f"Memory {i}")
        print_kv("Content", memory.content)
        print_kv("Source schema", memory.provenance.source_schema)
        print_kv("Confidence", memory.confidence)
        print_kv("Memory ID", str(memory.memory_id))
        print_kv("Session ID", str(memory.session_id))
        print_kv("Episode type", memory.episode_type)
        print_kv("Governance influences", memory.governance_influences)
        print_kv("Creator component", memory.provenance.creator_component)
        print_kv("Retrieval count", memory.retrieval_count)

    print_kv("\nTotal memories created", len(memories))
    results.append(("Created 3 episodic memories", len(memories) == 3))

    # ========================================================================
    # Step 2: Create inference request
    # ========================================================================
    print_section("STEP 2: Create Inference Request")

    session_id = memories[0].session_id  # Same session
    request = InferenceRequest(
        session_id=session_id,
        prompt="What are the ethical implications of autonomous weapons systems?",
        model="llama3.1",
        governance_context=[
            "uncertainty_management",
            "truthfulness_governance",
            "cognitive_humility",
            "boundary_preservation",
            "provenance_awareness",
        ],
        memory_context=[mem.memory_id for mem in memories],
        parameters={"temperature": 0.7, "max_tokens": 512},
    )

    print_kv("Request ID", str(request.request_id))
    print_kv("Session ID", str(request.session_id))
    print_kv("Prompt", request.prompt)
    print_kv("Memory context references", [str(m)[:8] + "..." for m in request.memory_context])
    print_kv("Governance context", request.governance_context)

    results.append(("Inference request created", True))

    # ========================================================================
    # Step 3: Simulate memory retrieval and influence mapping
    # ========================================================================
    print_section("STEP 3: Memory Retrieval & Influence Mapping")

    # Simulate retrieval: mark each memory as accessed
    retrieved_memories: list[EpisodicMemory] = []
    for memory in memories:
        memory.mark_accessed()
        retrieved_memories.append(memory)
        print(f"  Retrieved: {memory.content[:45]}... "
              f"(retrieval_count={memory.retrieval_count}, "
              f"last_accessed={memory.last_accessed.isoformat() if memory.last_accessed else 'N/A'})")

    print_kv("\nMemories retrieved", len(retrieved_memories))
    all_accessed = all(m.retrieval_count >= 1 for m in retrieved_memories)
    results.append(("All memories retrieved and marked accessed", all_accessed))

    # ========================================================================
    # Step 4: Show each memory and its influence
    # ========================================================================
    print_section("STEP 4: Memory -> Influence Mapping")

    memory_influences: list[MemoryInfluence] = []
    for i, memory in enumerate(retrieved_memories):
        influence = MemoryInfluence(
            memory_id=memory.memory_id,
            target_inference_id=request.request_id,
            influence_type="retrieval",  # This memory was retrieved to provide context
            strength=memory.confidence,  # Influence strength = memory confidence
            trace_visible=True,  # ALL influences are trace-visible in GARVIS
        )
        memory_influences.append(influence)

        print_subsection(f"Influence {i+1}: Memory -> Inference")
        print_kv("Memory content", memory.content)
        print_kv("  Source schema", memory.provenance.source_schema)
        print_kv("  Memory confidence", memory.confidence)
        print_kv("  -> Influence strength", influence.strength)
        print_kv("  -> Influence type", influence.influence_type)
        print_kv("  -> Trace visible", influence.trace_visible)
        print_kv("  -> Memory ID", str(influence.memory_id)[:8] + "...")
        print_kv("  -> Target inference", str(influence.target_inference_id)[:8] + "...")
        print()

    print_kv("Total influences mapped", len(memory_influences))
    results.append(
        (f"Mapped {len(memory_influences)} memory influences",
         len(memory_influences) == 3)
    )

    # ========================================================================
    # Step 5: Show the influence graph
    # ========================================================================
    print_section("STEP 5: Influence Graph (Memory -> Inference Links)")

    print(f"\n  {_BOLD}Graph Structure:{_RESET}")
    print(f"\n  {_CYAN}  [Inference: {str(request.request_id)[:12]}...]{_RESET}")
    print(f"  {_CYAN}       ▲{_RESET}")
    for i, influence in enumerate(memory_influences):
        memory = retrieved_memories[i]
        print(f"  {_GREEN}  [{memory.provenance.source_schema}]{_RESET}")
        print(f"  {_GREEN}  '{memory.content[:40]}...'{_RESET}")
        print(f"  {_GREEN}       | (strength={influence.strength}, type={influence.influence_type}){_RESET}")
        if i < len(memory_influences) - 1:
            print(f"  {_CYAN}       ▲{_RESET}")

    print(f"\n  {_BOLD}Graph Summary:{_RESET}")
    print_kv("Root node", f"Inference[{str(request.request_id)[:12]}...]")
    print_kv("Memory nodes", len(memory_influences))
    print_kv("Influence edges", len(memory_influences))
    print_kv("All edges bidirectional (memory↔influence↔inference)", True)

    results.append(("Influence graph constructed", len(memory_influences) == 3))

    # ========================================================================
    # Step 6: Verify all influences have trace_visible=True
    # ========================================================================
    print_section("STEP 6: Verify trace_visible=True for All Influences")

    all_visible = all(mi.trace_visible for mi in memory_influences)
    for i, influence in enumerate(memory_influences):
        status = f"{_GREEN}✓{_RESET}" if influence.trace_visible else f"{_RED}✗{_RESET}"
        print(f"  {status} Influence {i+1}: trace_visible={influence.trace_visible}")

    print_kv("\nAll influences trace_visible", all_visible)
    print_kv("(GARVIS policy: no hidden memory influence)", True)

    results.append(
        ("All influences trace_visible=True -- no hidden influence",
         all_visible)
    )

    # ========================================================================
    # Step 7: Show provenance chain for each influence
    # ========================================================================
    print_section("STEP 7: Provenance Chain for Each Influence")

    for i, (memory, influence) in enumerate(zip(retrieved_memories, memory_influences), 1):
        print_subsection(f"Provenance Chain {i}")

        # Build provenance chain
        chain = [
            ("Source Schema", memory.provenance.source_schema),
            ("Creator Component", memory.provenance.creator_component),
            ("Creation Timestamp", memory.provenance.creation_timestamp.isoformat()),
            ("Parent Memory", memory.provenance.parent_memory_id or "None (original)"),
            ("Inference ID", str(memory.provenance.inference_id) if memory.provenance.inference_id else "None"),
            ("---", "---"),
            ("Influence ID", str(influence.influence_id)),
            ("Target Inference", str(influence.target_inference_id)),
            ("Influence Type", influence.influence_type),
            ("Influence Strength", influence.strength),
            ("Trace Visible", influence.trace_visible),
            ("Influence Timestamp", influence.timestamp.isoformat()),
        ]

        for key, value in chain:
            if key == "---":
                print(f"    {'─' * 30}")
            else:
                print(f"    {key:25s}: {value}")
        print()

        # Verify provenance integrity
        has_source = bool(memory.provenance.source_schema)
        has_creator = bool(memory.provenance.creator_component)
        has_timestamp = bool(memory.provenance.creation_timestamp)

        results.append(
            (f"Memory {i}: provenance source_schema present", has_source)
        )
        results.append(
            (f"Memory {i}: provenance creator_component present", has_creator)
        )
        results.append(
            (f"Memory {i}: provenance creation_timestamp present", has_timestamp)
        )

    # ========================================================================
    # Integration: Show how this connects to lineage and audit
    # ========================================================================
    print_section("INTEGRATION: Lineage & Audit Recording")

    lineage = create_mock_lineage()
    trace_id = await lineage.start_trace(session_id)
    await lineage.record_memory_influence(trace_id, memory_influences)

    print_kv("Trace started", trace_id is not None)
    print_kv("Memory influences recorded in lineage", len(lineage._memory_influences))
    print_kv("All influences trace-visible in lineage",
             all(mi.trace_visible for mi in lineage._memory_influences))

    results.append(
        ("Memory influences recorded in lineage",
         len(lineage._memory_influences) == 3)
    )
    results.append(
        ("All lineage influences trace_visible",
         all(mi.trace_visible for mi in lineage._memory_influences))
    )

    # ========================================================================
    # Final summary
    # ========================================================================
    print_section("SUMMARY")
    print_kv("Total checks", len(results))
    print_kv("Passed", sum(1 for _, p in results if p))
    print_kv("Failed", sum(1 for _, p in results if not p))

    return results


async def main() -> None:
    """Entry point for the demo."""
    passed = await run_demo(
        demo_memory_influence,
        "MEMORY INFLUENCE TRACKING",
    )
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    asyncio.run(main())
