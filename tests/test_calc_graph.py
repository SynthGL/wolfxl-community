"""Tests for wolfxl.calc dependency graph and topological ordering."""

from __future__ import annotations

import pytest
from wolfxl.calc._graph import DependencyGraph


class TestAddFormula:
    def test_simple_dependency(self) -> None:
        g = DependencyGraph()
        g.add_formula("Sheet1!B1", "=Sheet1!A1+1", "Sheet1")
        assert "Sheet1!A1" in g.dependencies["Sheet1!B1"]
        assert "Sheet1!B1" in g.dependents["Sheet1!A1"]

    def test_range_dependency(self) -> None:
        g = DependencyGraph()
        g.add_formula("Sheet1!A4", "=SUM(A1:A3)", "Sheet1")
        deps = g.dependencies["Sheet1!A4"]
        assert "Sheet1!A1" in deps
        assert "Sheet1!A2" in deps
        assert "Sheet1!A3" in deps

    def test_cross_sheet_dependency(self) -> None:
        g = DependencyGraph()
        g.add_formula("IS!B1", "=TB!A1+TB!A2", "IS")
        deps = g.dependencies["IS!B1"]
        assert "TB!A1" in deps
        assert "TB!A2" in deps


class TestTopologicalOrder:
    def test_empty(self) -> None:
        g = DependencyGraph()
        assert g.topological_order() == []

    def test_linear_chain(self) -> None:
        """A1 -> B1 -> C1 (B1=A1+1, C1=B1*2)"""
        g = DependencyGraph()
        g.add_formula("Sheet1!B1", "=Sheet1!A1+1", "Sheet1")
        g.add_formula("Sheet1!C1", "=Sheet1!B1*2", "Sheet1")
        order = g.topological_order()
        assert order.index("Sheet1!B1") < order.index("Sheet1!C1")

    def test_diamond(self) -> None:
        """A1 feeds B1 and C1, both feed D1."""
        g = DependencyGraph()
        g.add_formula("Sheet1!B1", "=Sheet1!A1+1", "Sheet1")
        g.add_formula("Sheet1!C1", "=Sheet1!A1*2", "Sheet1")
        g.add_formula("Sheet1!D1", "=Sheet1!B1+Sheet1!C1", "Sheet1")
        order = g.topological_order()
        # B1 and C1 must come before D1
        assert order.index("Sheet1!B1") < order.index("Sheet1!D1")
        assert order.index("Sheet1!C1") < order.index("Sheet1!D1")

    def test_circular_detection(self) -> None:
        g = DependencyGraph()
        g.add_formula("Sheet1!A1", "=Sheet1!B1+1", "Sheet1")
        g.add_formula("Sheet1!B1", "=Sheet1!A1+1", "Sheet1")
        with pytest.raises(ValueError, match="Circular reference"):
            g.topological_order()

    def test_multi_sheet_ordering(self) -> None:
        """TB!C1 depends on IS!A1 which depends on TB!B1."""
        g = DependencyGraph()
        g.add_formula("IS!A1", "=TB!B1*0.1", "IS")
        g.add_formula("TB!C1", "=IS!A1+100", "TB")
        order = g.topological_order()
        assert order.index("IS!A1") < order.index("TB!C1")


class TestAffectedCells:
    def test_single_change(self) -> None:
        """Changing A1 affects B1 which affects C1."""
        g = DependencyGraph()
        g.add_formula("Sheet1!B1", "=Sheet1!A1+1", "Sheet1")
        g.add_formula("Sheet1!C1", "=Sheet1!B1*2", "Sheet1")
        affected = g.affected_cells({"Sheet1!A1"})
        assert affected == ["Sheet1!B1", "Sheet1!C1"]

    def test_diamond_propagation(self) -> None:
        g = DependencyGraph()
        g.add_formula("Sheet1!B1", "=Sheet1!A1+1", "Sheet1")
        g.add_formula("Sheet1!C1", "=Sheet1!A1*2", "Sheet1")
        g.add_formula("Sheet1!D1", "=Sheet1!B1+Sheet1!C1", "Sheet1")
        affected = g.affected_cells({"Sheet1!A1"})
        # All three formula cells are affected
        assert len(affected) == 3
        assert affected[-1] == "Sheet1!D1"

    def test_unrelated_cells_not_affected(self) -> None:
        g = DependencyGraph()
        g.add_formula("Sheet1!B1", "=Sheet1!A1+1", "Sheet1")
        g.add_formula("Sheet1!D1", "=Sheet1!C1*2", "Sheet1")
        affected = g.affected_cells({"Sheet1!A1"})
        assert "Sheet1!B1" in affected
        assert "Sheet1!D1" not in affected

    def test_change_non_existent_cell(self) -> None:
        g = DependencyGraph()
        g.add_formula("Sheet1!B1", "=Sheet1!A1+1", "Sheet1")
        affected = g.affected_cells({"Sheet1!Z99"})
        assert affected == []


class TestMaxDepth:
    def test_linear_chain_depth(self) -> None:
        g = DependencyGraph()
        g.add_formula("Sheet1!B1", "=Sheet1!A1+1", "Sheet1")
        g.add_formula("Sheet1!C1", "=Sheet1!B1*2", "Sheet1")
        g.add_formula("Sheet1!D1", "=Sheet1!C1+3", "Sheet1")
        assert g.max_depth({"Sheet1!A1"}) == 3

    def test_diamond_depth(self) -> None:
        g = DependencyGraph()
        g.add_formula("Sheet1!B1", "=Sheet1!A1+1", "Sheet1")
        g.add_formula("Sheet1!C1", "=Sheet1!A1*2", "Sheet1")
        g.add_formula("Sheet1!D1", "=Sheet1!B1+Sheet1!C1", "Sheet1")
        assert g.max_depth({"Sheet1!A1"}) == 2

    def test_empty_roots(self) -> None:
        g = DependencyGraph()
        assert g.max_depth(set()) == 0

    def test_no_dependents(self) -> None:
        g = DependencyGraph()
        g.add_formula("Sheet1!B1", "=Sheet1!A1+1", "Sheet1")
        # A1 has one dependent (B1), depth = 1
        assert g.max_depth({"Sheet1!A1"}) == 1
        # C1 is not referenced by anyone
        assert g.max_depth({"Sheet1!C1"}) == 0
