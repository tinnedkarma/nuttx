"""
entrypoint for nxstyle module
"""
from pathlib import Path
import sys
import importlib.resources
import re

from abc import ABC, abstractmethod
from typing import Generator

from tree_sitter import Language, Parser, Tree, Node, Point, Query
from tree_sitter_language_pack import get_language, get_parser


class Checker(ABC):
    """
    Base class for analyzing and processing syntax trees.
    This class is needed to avoid a single monolitic class checking
    all filetypes such as c/cpp headers/sources

    :param tree: The Tree-sitter syntax tree to analyze.
    :type tree: Tree
    :param parser: The Tree-sitter parser instance.
    :type parser: Parser
    :param lang: The Tree-sitter language instance.
    :type lang: Language
    :param scm: File name holding Tree-sitter queries
    "type scm: String
    """
    def __init__(self, file: Path, tree: Tree, parser: Parser, lang: Language, scm: str):
        self.file: Path = file
        self.tree: Tree = tree
        self.parser: Parser = parser
        self.lang: Language = lang

        try:
            with importlib.resources.open_text("nxtool.nxstyle.queries", scm) as f:
                queries: Query = self.lang.query(f.read())
        except FileNotFoundError as e:
            print(f"{e}")
            sys.exit(1)

        self.captures = queries.captures(self.tree.root_node)

    def walk_tree(self, node: Node | None = None) -> Generator[Node, None, None]:
        """
        Helper function to traverse the syntax tree in a depth-first manner, yielding each node.
        Traversing the tree is parser/language agnostic, 
        so this method should be part of the base class
        
        :param node: The starting node for traversal. If None, starts from the root.
        :type node: Node | None
        :yield: Nodes in the syntax tree.
        :rtype: Generator[Node, None, None]
        """
        if node is None:
            cursor = self.tree.walk()
        else:
            cursor = node.walk()

        visited_children = False

        while True:
            if not visited_children:
                yield cursor.node
                if not cursor.goto_first_child():
                    visited_children = True
            elif cursor.goto_next_sibling():
                visited_children = False
            elif not cursor.goto_parent():
                break

    def info(self, point: Point, text: str) -> str:
        return (
            f"{self.file.resolve()}:{point.row + 1}:{point.column}: "
            f"[INFO] "
            f"{text}")

    def warning(self, point: Point, text: str) -> str:
        return (
            f"{self.file.resolve()}:{point.row + 1}:{point.column}: "
            f"[WARNING] "
            f"{text}")

    def error(self, point: Point, text: str) -> str:
        return (
            f"{self.file.resolve()}:{point.row + 1}:{point.column}: "
            f"[ERROR] "
            f"{text}")

    def style_assert(self, check: bool, message: str) -> None:
        if check is True:
            print(message)

    @abstractmethod
    def check_style(self) -> None:
        """
        Entry point for each checker.
        This method should hold custom logic of checking files
        """

class CChecker(Checker):
    """
    Checker class for analyzing and processing syntax trees for c source files.
    """

    def __init__(self, file: Path, scm: str):

        try:
            with open(file.as_posix(), 'rb') as fd:
                src = fd.read()
        except FileNotFoundError as e:
            print(f"{e}")
            sys.exit(1)

        lang = get_language('c')
        parser = get_parser('c')
        tree = parser.parse(src)

        super().__init__(file, tree, parser, lang, scm)

    def check_style(self) -> None:
        if "function.body" in self.captures:
            for m in self.captures["function.body"]:
                for n in iter(m.named_children):
                    self.__check_indents(2, n)

        if "expression.paranthesis" in self.captures:
            for m in self.captures["expression.paranthesis"]:
                if m.parent.type in {
                    "if_statement",
                    "for_statement",
                    "while_statement",
                    "do_statement",
                    "switch_statement",
                }:
                    self.style_assert(
                        (m.start_point.column - m.prev_sibling.end_point.column) != 1,
                        self.error(
                            m.start_point, 
                            "There should be exacly one whitespace after keyword"
                        )
                    )

                self.__check_whitespaces(m)

        if "list.arguments" in self.captures:
            for m in self.captures["list.arguments"]:
                self.__check_whitespaces(m)

    def __check_indents(self, indent: int, node: Node):
        """
        Internal function that checks the indent depth at node level.
        Just the startpoint is checked, work for specific node should be defered.
        
        Only the subset of nodes checked here should increase indent depth.

        :param indent:
        :type indent: int
        :param node:
        :type node: Node 
        """
        match node.type:
            case "if_statement":
                self.__check_indents_if_statement(indent, node)
            case "for_statement":
                self.__check_indents_for_statement(indent, node)
            case "while_statement" | "do_statement":
                self.__check_indents_while_statement(indent, node)
            case "switch_statement":
                self.__check_indents_switch_statement(indent, node)
            case (
                "return_statement" |
                "expression_statement" |
                "declaration" | 
                "break_statement"
            ):
                for child in node.named_children:
                    self.__check_indents(indent + 2, child)
            case _:
                return

        self.style_assert(
            node.start_point.column != indent,
            self.error(node.start_point, "Wrong indentation")
        )

    def  __check_indents_if_statement(self, indent: int, node: Node) -> None:
        """
        Defered work for if statements.
        If statement node checks should take into account the node structure.
        Indent and alignments checks will be handled here

        Both consequence and alternative field can hold statemen child nodes
        
        """

        consequence: Node = node.child_by_field_name("consequence")
        alternative: Node | None = node.child_by_field_name("alternative")

        # Open braket should be on separate line
        self.style_assert(
            consequence.start_point.row == node.start_point.row,
            self.error(consequence.start_point, "Left bracket not on separate line")
        )

        # Open braket should be indented by two whitespaces
        self.style_assert(
            consequence.children[0].start_point.column != indent + 2,
            self.error(consequence.start_point, "Wrong indentation")
        )

        for n in consequence.named_children:
            self.__check_indents(indent + 4, n)

        # Close braket should be on separate line
        self.style_assert(
            consequence.children[-1].start_point.row == consequence.children[-2].start_point.row,
            self.error(consequence.start_point, "Left bracket not on separate line")
        )

        # Close braket should be indented by two whitespaces
        self.style_assert(
            consequence.children[-1].start_point.column != indent + 2,
            self.error(consequence.children[-1].start_point, "Wrong indentation")
        )

        if alternative is not None:

            # Else keyword should be aligned with if keyword
            self.style_assert(
                alternative.children[0].start_point.column != indent,
                self.error(alternative.start_point, "Wrong indentation")
            )

            if alternative.children[1].type == "if_statement":
                self.__check_indents_if_statement(indent, alternative.children[1])

            else:
                # Rest of the else body should be checked for indents
                self.__check_indents(indent, alternative.children[1])

    def  __check_indents_for_statement(self, indent: int, node: Node) -> None:

        body: Node = node.child_by_field_name("body")

        if body.type == "compound_statement":

            # Open braket should be on separate line
            self.style_assert(
                body.start_point.row == body.prev_sibling.start_point.row,
                self.error(body.start_point, "Left bracket not on separate line")
            )

            # Open braket should be indented by two whitespaces
            self.style_assert(
                body.start_point.column != indent + 2,
                self.error(body.start_point, "Wrong indentation")
            )

            for n in body.named_children:
                self.__check_indents(indent + 4, n)

            # Close braket should be on separate line
            self.style_assert(
                body.children[-1].start_point.row == body.children[-2].start_point.row,
                self.error(body.start_point, "Left bracket not on separate line")
            )

            # Close braket should be indented by two whitespaces
            self.style_assert(
                body.children[-1].start_point.column != indent + 2,
                self.error(body.children[-1].start_point, "Wrong indentation")
            )

        elif body.type == "expression_statement":

            if body.named_child_count == 0:
                self.style_assert(
                    body.prev_sibling.start_point.row != body.start_point.row,
                    self.error(body.start_point, "Empty body should be inline with last node")
                )

            else:
                for n in body.named_children:
                    self.__check_indents(indent + 4, n)

    def __check_indents_while_statement(self, indent: int, node: Node) -> None:

        body: Node = node.child_by_field_name("body")

        # Open braket should be on separate line
        self.style_assert(
            body.start_point.row == body.prev_sibling.start_point.row,
            self.error(body.start_point, "Left bracket not on separate line")
        )

        # Open braket should be indented by two whitespaces
        self.style_assert(
            body.start_point.column != indent + 2,
            self.error(body.start_point, "Wrong indentation")
        )

        for n in body.named_children:
            self.__check_indents(indent + 4, n)

        # Close braket should be on separate line
        self.style_assert(
            body.children[-1].start_point.row == body.children[-2].start_point.row,
            self.error(body.children[-1].start_point, "Left bracket not on separate line")
        )

        # Close braket should be indented by two whitespaces
        self.style_assert(
            body.children[-1].start_point.column != indent + 2,
            self.error(body.children[-1].start_point, "Wrong indentation")
        )

    def __check_indents_switch_statement(self, indent: int, node: Node) -> None:

        body: Node = node.child_by_field_name("body")

        # Open braket should be on separate line
        self.style_assert(
            body.start_point.row == body.prev_sibling.start_point.row,
            self.error(body.start_point, "Left bracket not on separate line")
        )

        # Open braket should be indented by two whitespaces
        self.style_assert(
            body.start_point.column != indent + 2,
            self.error(body.start_point, "Wrong indentation")
        )

        case_statements = ( n for n in body.named_children if n.type == "case_statement" )
        for n in case_statements:
            self.__check_indents_case_statement(indent + 4, n)

        # Close braket should be on separate line
        self.style_assert(
            body.children[-1].start_point.row == body.children[-2].start_point.row,
            self.error(body.start_point, "Left bracket not on separate line")
        )

        # Close braket should be indented by two whitespaces
        self.style_assert(
            body.children[-1].start_point.column != indent + 2,
            self.error(body.children[-1].start_point, "Wrong indentation")
        )

    def __check_indents_case_statement(self, indent: int, node: Node) -> None:

        kw: Node = node.children[0]
        offset: int = 3 if kw.type == "case" else 2
        body: Node = node.children[offset]

        self.style_assert(
            node.start_point.column != indent,
            self.error(node.start_point, "Wrong indentation")
        )

        if body.type == "compound_statement":
            # Open braket should be on separate line
            self.style_assert(
                body.start_point.row == body.prev_sibling.start_point.row,
                self.error(body.start_point, "Left bracket not on separate line")
            )

            # Open braket should be indented by two whitespaces
            self.style_assert(
                body.start_point.column != indent + 2,
                self.error(body.start_point, "Wrong indentation")
            )

            for n in body.named_children:
                self.__check_indents(indent + 4, n)

            # Close braket should be on separate line
            self.style_assert(
                body.children[-1].start_point.row == body.children[-2].start_point.row,
                self.error(body.start_point, "Left bracket not on separate line")
            )

            # Close braket should be indented by two whitespaces
            self.style_assert(
                body.children[-1].start_point.column != indent + 2,
                self.error(body.children[-1].start_point, "Wrong indentation")
            )
        else:
            for n in node.children[offset:]:
                self.__check_indents(indent + 2, n)

    def __check_whitespaces(self, node: Node) -> None:
        self.style_assert(
            bool(re.search(r"\(\s+", node.text.decode())),
            self.error(node.start_point, "Whitespace after open paranthesis")
        )

        self.style_assert(
            bool(re.search(r"\s+\)", node.text.decode())),
            self.error(node.start_point, "Whitespace before close paranthesis")
        )

        self.style_assert(
            bool(
                re.search(r"(?<!\s)(\|\||&&|<<=|>>=|[+\*\/%&|^<>!=]=)", node.text.decode())
            ),
            self.error(node.start_point, "Missing whitespaces before operator")
        )

        self.style_assert(
            bool(
                re.search(r"(\|\||&&|<<=|>>=|[+\*\/%&|^<>!=]=)(?!\s)", node.text.decode())
            ),
            self.error(node.start_point, "Missing whitespaces after operator")
        )

        self.style_assert(
            bool(
                re.search(
                    r",(?!\s)", 
                    re.sub(r"([\"\'].*?\")", "", node.text.decode())
                )
            ),
            self.error(node.start_point, "Missing whitespaces after comma")
        )
