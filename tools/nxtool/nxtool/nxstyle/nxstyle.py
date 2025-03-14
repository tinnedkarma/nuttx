"""
entrypoint for nxstyle module
"""
from pathlib import Path
import sys
import importlib.resources

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
        for m in self.captures["function.body"]:
            for n in iter(m.named_children):
                self.__check_indents(2, n)

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
            case "while_statement":
                self.__check_indents_while_statement(indent, node)
            case "switch_statement":
                self.__check_indents_switch_statement(indent, node)
            case (
                "return_statement" |
                "expression_statement"
            ):
                for child in node.named_children:
                    self.__check_indents(indent + 2, child)

                self.style_assert(
                    node.start_point.column != indent,
                    self.error(node.start_point, "Wrong indentation")
                )
            case _:
                return

    def  __check_indents_if_statement(self, indent: int, node: Node) -> None:
        """
        Defered work for if statements.
        If statement node checks should take into account the node structure.
        Indent and alignments checks will be handled here

        Both consequence and alternative field can hold statemen child nodes
        
        """

        # Unwrap if_statement node
        if_keyword: Node = node.children[0]
        condition: Node = node.child_by_field_name("condition")
        consequence: Node = node.child_by_field_name("consequence")
        alternative: Node | None = node.child_by_field_name("alternative")

        # Between "if" keyword and condition node should be an whitespace
        self.style_assert(
            (condition.start_point.column - if_keyword.end_point.column) != 1,
            self.error(if_keyword.end_point, "Missing whitespace after keyword")
        )

        # Open braket should be on separate line
        self.style_assert(
            consequence.children[0].start_point.row == condition.start_point.row,
            self.error(condition.start_point, "Left bracket not on separate line")
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
            self.error(condition.start_point, "Left bracket not on separate line")
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

            # Rest of the else body should be checked for indents
            self.__check_indents(indent, alternative.children[1])

    def  __check_indents_for_statement(self, indent: int, node: Node) -> None:

        align: bool = False
        align_start_point: Point | None = None

        # Unwrap for_statement node
        for_keyword: Node = node.children[0]
        initializer: Node | None = node.child_by_field_name("initializer")
        condition: Node | None = node.child_by_field_name("condition")
        update: Node | None = node.child_by_field_name("update")
        body: Node = node.child_by_field_name("body")

        # Between "for" keyword and condition node should be an whitespace
        self.style_assert(
            (for_keyword.next_sibling.start_point.column - for_keyword.end_point.column) != 1,
            self.error(for_keyword.end_point, "Missing whitespace after keyword")
        )

        if initializer is not None:

            align_start_point = initializer.start_point

            self.style_assert(
                (initializer.start_point.column - initializer.prev_sibling.end_point.column) != 0,
                self.error(initializer.end_point, "Missing whitespace after keyword")
            )

            self.style_assert(
                (initializer.next_sibling.start_point.column - initializer.end_point.column) != 0,
                self.error(initializer.end_point, "Operator must be next to an operand")
            )

        if condition is not None:

            self.style_assert(
                (condition.next_sibling.start_point.column - condition.end_point.column) != 0,
                self.error(condition.end_point, "Operator must be next to an operand")
            )

            if (
                align_start_point is not None and
                condition.start_point.row != align_start_point.row
            ):
                align = True
                self.style_assert(
                    condition.start_point.column != initializer.start_point.column,
                    self.error(condition.end_point, "Missaligned statements")
                )

            else:
                self.style_assert(
                    (condition.start_point.column - condition.prev_sibling.end_point.column) != 1,
                    self.error(condition.end_point, "Missing whitespace after keyword")
                )

        if update is not None:

            self.style_assert(
                (update.next_sibling.start_point.column - update.end_point.column) != 0,
                self.error(update.end_point, "Operator must be next to an operand")
            )

            if align is True:
                self.style_assert(
                    update.start_point.column != initializer.start_point.column,
                    self.error(update.end_point, "Missaligned statements")
                )
            else:
                self.style_assert(
                    (update.start_point.column - update.prev_sibling.end_point.column) != 1,
                    self.error(update.end_point, "Missing whitespace after keyword")
                )

        if body.type == "compound_statement":

            # Open braket should be on separate line
            self.style_assert(
                body.children[0].start_point.row == for_keyword.start_point.row,
                self.error(body.start_point, "Left bracket not on separate line")
            )

            # Open braket should be indented by two whitespaces
            self.style_assert(
                body.children[0].start_point.column != indent + 2,
                self.error(body.start_point, "Wrong indentation")
            )

            for n in body.named_children:
                self.__check_indents(indent + 4, n)

            # Close braket should be on separate line
            self.style_assert(
                body.children[-1].start_point.row == body.children[-2].start_point.row,
                self.error(condition.start_point, "Left bracket not on separate line")
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
                    self.error(condition.start_point, "Empty body should be inline with last node")
                )

            else:
                for n in body.named_children:
                    self.__check_indents(indent + 4, n)

    def __check_indents_while_statement(self, indent: int, node: Node) -> None:
        # Unwrap while_statement node
        while_keyword: Node = node.children[0]
        condition: Node = node.child_by_field_name("condition")
        body: Node = node.child_by_field_name("body")

        # Between "while" keyword and condition node should be an whitespace
        self.style_assert(
            (condition.start_point.column - while_keyword.end_point.column) != 1,
            self.error(while_keyword.end_point, "Missing whitespace after keyword")
        )

        # Open braket should be on separate line
        self.style_assert(
            body.children[0].start_point.row == condition.start_point.row,
            self.error(condition.start_point, "Left bracket not on separate line")
        )

        # Open braket should be indented by two whitespaces
        self.style_assert(
            body.children[0].start_point.column != indent + 2,
            self.error(body.start_point, "Wrong indentation")
        )

        for n in body.named_children:
            self.__check_indents(indent + 4, n)

        # Close braket should be on separate line
        self.style_assert(
            body.children[-1].start_point.row == body.children[-2].start_point.row,
            self.error(condition.start_point, "Left bracket not on separate line")
        )

        # Close braket should be indented by two whitespaces
        self.style_assert(
            body.children[-1].start_point.column != indent + 2,
            self.error(body.children[-1].start_point, "Wrong indentation")
        )

    def __check_indents_switch_statement(self, indent: int, node: Node) -> None:
        # Unwrap switch_statement node
        print(f"{node.start_point}")
        switch_keyword: Node = node.children[0]
        condition: Node = node.child_by_field_name("condition")
        body: Node = node.child_by_field_name("body")

        # Between "while" keyword and condition node should be an whitespace
        self.style_assert(
            (condition.start_point.column - switch_keyword.end_point.column) != 1,
            self.error(switch_keyword.end_point, "Missing whitespace after keyword")
        )

        # Open braket should be on separate line
        self.style_assert(
            body.children[0].start_point.row == switch_keyword.start_point.row,
            self.error(body.start_point, "Left bracket not on separate line")
        )

        # Open braket should be indented by two whitespaces
        self.style_assert(
            body.children[0].start_point.column != indent + 2,
            self.error(body.start_point, "Wrong indentation")
        )

        case_statements = ( n for n in body.named_children if n.type == "case_statement" )
        for n in case_statements:
            self.__check_indents_case_statement(indent + 4, n)

        # Close braket should be on separate line
        self.style_assert(
            body.children[-1].start_point.row == body.children[-2].start_point.row,
            self.error(condition.start_point, "Left bracket not on separate line")
        )

        # Close braket should be indented by two whitespaces
        self.style_assert(
            body.children[-1].start_point.column != indent + 2,
            self.error(body.children[-1].start_point, "Wrong indentation")
        )

    def __check_indents_case_statement(self, indent: int, node: Node) -> None:
        # Unwrap switch_statement node
        case_keyword: Node = node.children[0]
        value: Node = node.child_by_field_name("value")

        self.style_assert(
            node.start_point.column != indent,
            self.error(node.start_point, "Wrong indentation")
        )

        if case_keyword.type == "case":

            # Between "case" keyword and value node should be an whitespace
            self.style_assert(
                (value.start_point.column - case_keyword.end_point.column) != 1,
                self.error(value.end_point, "Missing whitespace after keyword")
            )

            self.style_assert(
                (value.next_sibling.start_point.column - value.end_point.column) != 0,
                self.error(value.next_sibling.end_point, "Missing whitespace after keyword")
            )
        else:
            self.style_assert(
                (case_keyword.next_sibling.start_point.column - case_keyword.end_point.column) != 0,
                self.error(case_keyword.next_sibling.end_point, "Missing whitespace after keyword")
            )

        for n in node.children[3:]:
            self.__check_indents(indent + 2, n)
