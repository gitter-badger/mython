#! /usr/bin/env python
# ______________________________________________________________________
'''
Moderately updated port from Basil of
basil.lang.mython.myfront_transformer.MyHandler.

The MyHandler class implements a transformer from Python concrete
parse trees to Python abstract syntax trees.

TODO: Port to using cst.ConcreteNodeTransformer().
'''
# ______________________________________________________________________
# Module imports

import ast
import token

# ______________________________________________________________________
# Class definition

class MyHandler(object):
    def __init__ (self, *args, **kws):
        self.expr_context = ast.Load

    def handle_node (self, node):
        handler_name = "handle_%s" % (str(node[0]),)
        handler = getattr(self, handler_name, self.handle_default)
        return handler(node)

    def handle_children (self, node):
        return [self.handle_node(child) for child in node[1]]

    def is_token (self, node):
        return type(node[0]) == tuple

    def handle_default (self, node):
        return node[0]

    def _handle_nontoken_children (self, node):
        return [self.handle_node(child) for child in node[1]
                if not self.is_token(child)]

    def _handle_only_child (self, node):
        children = node[1]
        assert len(children) == 1
        return self.handle_node(children[0])

    def _flatten_once (self, ast_list):
        ret_val = []
        for ast_elem in ast_list:
            if type(ast_elem) == list:
                ret_val += ast_elem
            else:
                ret_val.append(ast_elem)
        return ret_val

    def _handle_left_binop (self, node, construct_op):
        children = node[1]
        if len(children) > 1:
            child_results = [self.handle_node(child) for child in children]
            location = self._get_location(node)
            op = construct_op(child_results[1])
            ret_val = ast.BinOp(child_results[0], op, child_results[2],
                                lineno=location[0], col_offset=location[1])
            for child_index in range(4, len(child_results), 2):
                location = child_results[child_index - 1][2]
                op = construct_op(child_results[child_index - 1])
                ret_val = ast.BinOp(ret_val, op, child_results[child_index],
                                    lineno=location[0],
                                    col_offset=location[1])
        else:
            ret_val = self.handle_node(children[0])
        return ret_val

    def _handle_logical_op (self, node, op_constructor):
        children = node[1]
        if len(children) > 1:
            child_results = [self.handle_node(child) for child in children]
            location = self._get_location(node)
            ret_val = ast.BoolOp(op_constructor(),
                                 [child for child in child_results
                                  if isinstance(child, ast.AST)],
                                 lineno=location[0], col_offset=location[1])
        else:
            ret_val = self.handle_node(children[0])
        return ret_val

    def _get_location (self, node):
        is_token = self.is_token
        while not is_token(node):
            node = node[1][0]
        return node[0][2]

    def _get_tokens (self, node):
        if self.is_token(node):
            yield node[0]
        else:
            child_stack = node[1][:]
            child_stack.reverse()
            while child_stack:
                crnt_node = child_stack.pop()
                if self.is_token(crnt_node):
                    yield crnt_node[0]
                else:
                    crnt_children = crnt_node[1][:]
                    crnt_children.reverse()
                    child_stack.extend(crnt_children)

    def _handle_comp_for (self, node):
        children = node[1]
        old_context = self.expr_context
        self.expr_context = ast.Store
        target = self.handle_node(children[1])
        self.expr_context = old_context
        iter_expr = self.handle_node(children[3])
        child_ifs = []
        comprehensions = []
        if len(children) > 4:
            child_ifs, comprehensions = self.handle_node(children[4])
        comprehensions.insert(0, ast.comprehension(target, iter_expr,
                                                   child_ifs))
        return ([], comprehensions)

    def _handle_comp_if (self, node):
        children = node[1]
        if_expr = self.handle_node(children[1])
        peer_ifs = []
        comprehensions = []
        if len(children) > 2:
            peer_ifs, comprehensions = self.handle_node(children[2])
        peer_ifs.insert(0, if_expr)
        return (peer_ifs, comprehensions)

    def handle_and_expr (self, node):
        return self._handle_left_binop(node, lambda x : ast.BitAnd())

    def handle_and_test (self, node):
        return self._handle_logical_op(node, ast.And)

    def handle_arglist (self, node):
        """handle_arglist() - Should return a 4-element list with the
        argument related inputs to the Call constructor."""
        args = []
        keywords = []
        starargs = None
        kwargs = None
        children = node[1]
        child_count = len(children)
        child_index = 0
        while ((child_index < child_count) and
               (not self.is_token(children[child_index]))):
            child_result = self.handle_node(children[child_index])
            if isinstance(child_result, ast.keyword):
                keywords.append(child_result)
                child_index += 2
                break
            args.append(child_result)
            child_index += 2
        while ((child_index < child_count) and
               (not self.is_token(children[child_index]))):
            child_result = self.handle_node(children[child_index])
            if not isinstance(child_result, ast.keyword):
                # XXX Typical syntax error notes.
                raise SyntaxError("non-keyword arg after keyword arg")
            keywords.append(child_result)
            child_index += 2
        if ((child_index < child_count) and
            self.is_token(children[child_index]) and
            children[child_index][0][1] == "*"):
            starargs = self.handle_node(children[child_index + 1])
            child_index += 3
        if ((child_index < child_count) and
            self.is_token(children[child_index]) and
            children[child_index][0][1] == "**"):
            kwargs = self.handle_node(children[child_index + 1])
            child_index += 3
        # XXX Additional checks required here?
        return [args, keywords, starargs, kwargs]

    def handle_argument (self, node):
        children = node[1]
        if len(children) == 1:
            ret_val = self.handle_node(children[0])
        else:
            if children[1][0][1] == '=':
                # Keyword argument.
                assert len(children) == 3
                lhs = self.handle_node(children[0])
                if not isinstance(lhs, ast.Name):
                    # XXX This error message is what Python says.
                    raise SyntaxError("keyword can't be an expression")
                lhs_keyword = lhs.id
                rhs = self.handle_node(children[2])
                ret_val = ast.keyword(lhs_keyword, rhs)
            else:
                # Generator argument.
                location = self._get_location(children[0])
                target = self.handle_node(children[0])
                if_exprs, comprehensions = self.handle_node(children[1])
                assert len(if_exprs) == 0
                ret_val = ast.GeneratorExp(
                    target, comprehensions, 
                    lineno=location[0], col_offset=location[1])
        return ret_val

    def handle_arith_expr (self, node):
        def arith_op (tok):
            return ast.Add() if tok[1] == "+" else ast.Sub()
        return self._handle_left_binop(node, arith_op)

    def handle_assert_stmt (self, node):
        children = node[1]
        assert self.is_token(children[0])
        location = children[0][0][2]
        child_results = self._handle_nontoken_children(node)
        if len(child_results) == 1:
            test = child_results[0]
            msg = None
        else:
            test, msg = child_results
        return ast.Assert(test, msg,
                          lineno=location[0], col_offset=location[1])

    def handle_atom (self, node):
        ret_val = None
        children = node[1]
        assert self.is_token(children[0])
        token_text = children[0][0][1]
        token_location = children[0][0][2]
        if token_text == "(":
            if self.is_token(children[1]) and children[1][0][1] == ")":
                if self.expr_context is not ast.Load:
                    # XXX Figure out how to push stack frame for
                    # traceback from Python.
                    raise NotImplementedError()
                ret_val = ast.Tuple(
                    [], ast.Load(),
                    lineno=token_location[0], col_offset=token_location[1])
            else:
                # NOTE: This puts the burden of detecting a tuple and
                # constructing it on handle_testlist_gexp().
                ret_val = self.handle_node(children[1])
        elif token_text == "[":
            if self.is_token(children[1]) and children[1][0][1] == "]":
                if self.expr_context is not ast.Load:
                    # XXX Figure out how to push stack frame for
                    # traceback from Python.
                    raise NotImplementedError()
                ret_val = ast.List(
                    [], ast.Load(),
                    lineno=token_location[0], col_offset=token_location[1])
            else:
                ret_val = self.handle_node(children[1])
                if hasattr(ret_val, "lineno") and ret_val.lineno is None:
                    ret_val.lineno, ret_val.col_offset = token_location
        elif token_text == "{":
            if self.expr_context is not ast.Load:
                raise NotImplementedError()
            if self.is_token(children[1]) and children[1][0][1] == "}":
                ret_val = ast.Dict([], [], lineno=token_location[0],
                                   col_offset=token_location[1])
            else:
                ret_val = self.handle_node(children[1])
                if hasattr(ret_val, "lineno"):
                    ret_val.lineno = token_location[0]
                if hasattr(ret_val, "col_offset"):
                    ret_val.col_offset = token_location[1]
        elif token_text == "`":
            assert children[2][0][1] == "`"
            ret_val = ast.Repr(self.handle_node(children[1]),
                               lineno=token_location[0],
                               col_offset=token_location[1])
        else:
            token_kind = children[0][0][0]
            if token_kind == token.STRING:
                ret_string = eval(token_text)
                for child in children[1:]:
                    ret_string += eval(child[0][1])
                ret_val = ast.Str(ret_string, lineno=token_location[0],
                                  col_offset=token_location[1])
            elif token_kind == token.NUMBER:
                ret_val = ast.Num(eval(token_text), lineno=token_location[0],
                                  col_offset=token_location[1])
            else:
                assert token_kind == token.NAME
                ret_val = ast.Name(token_text, self.expr_context(),
                                   lineno=token_location[0],
                                   col_offset=token_location[1])
        return ret_val

    def handle_augassign (self, node):
        children = node[1]
        token_text = children[0][0][1]
        return {'+=' : ast.Add,
                '-=' : ast.Sub,
                '*=' : ast.Mult,
                '/=' : ast.Div,
                '%=' : ast.Mod,
                '&=' : ast.BitAnd,
                '|=' : ast.BitOr,
                '^=' : ast.BitXor,
                '<<=' : ast.LShift,
                '>>=' : ast.RShift,
                '**=' : ast.Pow,
                '//=' : ast.FloorDiv}[token_text]()

    def handle_break_stmt (self, node):
        location = node[1][0][0][2]
        return ast.Break(lineno=location[0], col_offset=location[1])

    def handle_classdef (self, node):
        children = node[1]
        location = children[0][0][2]
        class_name = children[1][0][1]
        bases = []
        decorators = []
        if self.is_token(children[2]) and children[2][0][1] == "(":
            if not self.is_token(children[3]):
                bases = self.handle_node(children[3])
                if type(bases) != ast.Tuple:
                    # No comma, causing handle_testlist() to return
                    # the sole child.
                    # XXX Should handle_testlist() return a list
                    # unconditionally, and be added to the list of
                    # nodes that can't be simplified?
                    bases = [bases]
                else:
                    bases = bases.elts
        return ast.ClassDef(class_name, bases, self.handle_node(children[-1]),
                            decorators, # FIXME: Handle class decorators.
                            lineno=location[0], col_offset=location[1])

    def handle_comp_for (self, node):
        return self.handle_gen_for(node)

    def handle_comp_if (self, node):
        return self.handle_gen_if(node)

    def handle_comp_iter (self, node):
        return self.handle_gen_iter(node)

    def handle_comp_op (self, node):
        children = node[1]
        token_text = children[0][0][1]
        if len(children) == 1:
            ret_val = {'<': ast.Lt,
                       '>': ast.Gt,
                       '==': ast.Eq,
                       '>=': ast.GtE,
                       '<=': ast.LtE,
                       '<>': ast.NotEq,
                       '!=': ast.NotEq,
                       'in': ast.In,
                       'is' : ast.Is}[token_text]()
        elif token_text == "is":
            ret_val = ast.IsNot()
        else:
            assert token_text == "not"
            ret_val = ast.NotIn()
        return ret_val

    def handle_comparison (self, node):
        children = node[1]
        left = self.handle_node(children[0])
        if len(children) == 1:
            ret_val = left
        else:
            ops = []
            comparators = []
            for child_index in xrange(1, len(children), 2):
                ops.append(self.handle_node(children[child_index]))
                comparators.append(self.handle_node(children[child_index + 1]))
            lineno = None
            col_offset = None
            if hasattr(left, "lineno"):
                lineno = left.lineno
                col_offset = left.col_offset
            ret_val = ast.Compare(left, ops, comparators, lineno=lineno,
                                  col_offset=col_offset)
        return ret_val

    handle_compound_stmt = _handle_only_child

    def handle_continue_stmt (self, node):
        location = node[1][0][0][2]
        return ast.Continue(lineno=location[0], col_offset=location[1])

    def handle_decorated (self, node):
        raise NotImplementedError(repr(node))

    def handle_decorator (self, node):
        children = node[1]
        ret_val = self.handle_node(children[1])
        child_count = len(children)
        if child_count > 3:
            location = children[0][0][2]
            args = [ret_val]
            if child_count > 5:
                args += self.handle_node(children[3])
            else:
                args += [[], [], None, None]
            args += location
            ret_val = ast.Call(*args)
        return ret_val

    handle_decorators = handle_children

    def handle_del_stmt (self, node):
        children = node[1]
        location = children[0][0][2]
        old_context = self.expr_context
        self.expr_context = ast.Del
        targets = self.handle_node(children[1])
        self.expr_context = old_context
        if type(targets) != ast.Tuple:
            # XXX This has a similar flavor to the handle_testlist()
            # notes; see handle_classdef() in the base class handling.
            targets = [targets]
        else:
            targets = targets.elts
        return ast.Delete(targets, location[0], location[1])

    def handle_dictmaker (self, node):
        children = node[1]
        keys = []
        values = []
        assert len(children) > 2
        for child_index in xrange(0, len(children), 4):
            keys.append(self.handle_node(children[child_index]))
            assert children[child_index + 1][0][1] == ':'
            values.append(self.handle_node(children[child_index + 2]))
        # Note: The location is going to be set by handle_atom().
        return ast.Dict(keys, values)

    def handle_dictorsetmaker (self, node):
        try:
            return self.handle_dictmaker(node)
        except:
            raise NotImplementedError(repr(node))

    def handle_dotted_as_name (self, node):
        children = node[1]
        module_name = ""
        for token in self._get_tokens(children[0]):
            module_name += token[1]
        module_alias = None
        if len(children) > 1:
            # XXX Unsure about where 'dotted_name NAME NAME' is legal...
            assert children[1][0][1] == "as"
            module_alias = children[2][0][1]
        return ast.alias(module_name, module_alias)

    handle_dotted_as_names = _handle_nontoken_children

    def handle_dotted_name (self, node):
        """Note: This is circumvented by handle_dotted_as_name()!"""
        # XXX Not sure this has the 100% fidelity I want.
        children = node[1]
        first_name = children[0][0][1]
        first_location = children[0][0][2]
        ret_val = ast.Name(first_name, ast.Load(), first_location[0],
                           first_location[1])
        for child_index in xrange(2, len(children), 2):
            location = children[child_index - 1][0][2]
            ret_val = ast.Attribute(ret_val, children[child_index][0][1],
                                    ast.Load(), *location)
        return ret_val

    def handle_encoding_decl (self, node):
        raise NotImplementedError("should not be reachable in grammar!")

    def handle_eval_input (self, node):
        ret_val = self.handle_node(node[1][0])
        return ret_val

    def handle_except_clause (self, node):
        ret_val = []
        children = node[1][1:]
        if len(children) > 0:
            ret_val.append(self.handle_node(children[0]))
            if len(children) > 1:
                old_context = self.expr_context
                self.expr_context = ast.Store
                ret_val.append(self.handle_node(children[2]))
                self.expr_context = old_context
        return ret_val

    def handle_exec_stmt (self, node):
        children = node[1]
        location = children[0][0][2]
        body = self.handle_node(children[1])
        global_expr = None
        local_expr = None
        if len(children) > 2:
            global_expr = self.handle_node(children[3])
            if len(children) > 4:
                local_expr = self.handle_node(children[5])
        return ast.Exec(body, global_expr, local_expr, *location)

    def handle_expr (self, node):
        return self._handle_left_binop(node, lambda tok : ast.BitOr())

    def handle_expr_stmt (self, node):
        children = node[1]
        if len(children) == 1:
            location = self._get_location(children[0])
            ret_val = ast.Expr(
                self.handle_node(children[0]), lineno=location[0],
                col_offset=location[1])
        elif not self.is_token(children[1]):
            assert len(children) == 3
            # Augmented assignment
            location = self._get_location(children[0])
            old_context = self.expr_context
            self.expr_context = ast.Store
            lhs = self.handle_node(children[0])
            self.expr_context = old_context
            aug_op = self.handle_node(children[1])
            rhs = self.handle_node(children[2])
            ret_val = ast.AugAssign(lhs, aug_op, rhs,
                                    lineno=location[0], col_offset=location[1])
        else:
            location = self._get_location(children[0])
            old_context = self.expr_context
            self.expr_context = ast.Store
            targets = [self.handle_node(child) for child in children[:-1]
                       if not self.is_token(child)]
            self.expr_context = old_context
            value = self.handle_node(children[-1])
            ret_val = ast.Assign(targets, value,
                                 lineno=location[0], col_offset=location[1])
        return ret_val

    def handle_exprlist (self, node):
        children = node[1]
        if len(children) == 1:
            ret_val = self.handle_node(children[0])
        else:
            location = self._get_location(children[0])
            tup_elems = self._handle_nontoken_children(node)
            ret_val = ast.Tuple(tup_elems, self.expr_context(),
                                lineno=location[0],
                                col_offset=location[1])
        return ret_val

    def handle_factor (self, node):
        children = node[1]
        if len(children) > 1:
            token = children[0][0]
            token_text = token[1]
            token_location = token[2]
            unary_op_constructor = {"+" : ast.UAdd,
                                    "-" : ast.USub,
                                    "~" : ast.Invert}[token_text]
            ret_val = ast.UnaryOp(unary_op_constructor(),
                                  self.handle_node(children[1]),
                                  lineno=token_location[0],
                                  col_offset=token_location[1])
        else:
            ret_val = self.handle_node(children[0])
        return ret_val

    def handle_file_input (self, node):
        child_results = self._handle_nontoken_children(node)
        return ast.Module(self._flatten_once(child_results))

    handle_flow_stmt = _handle_only_child

    def handle_for_stmt (self, node):
        children = node[1]
        location = self._get_location(children[0])
        old_context = self.expr_context
        self.expr_context = ast.Store
        target = self.handle_node(children[1])
        self.expr_context = old_context
        # XXX Compatibility hack to comply with Python - which seems
        # to only apply in a weird situations...WTF, yo?
        if isinstance(target, ast.Tuple):
            target.col_offset = location[1]
        iter_expr = self.handle_node(children[3])
        body_stmts = self.handle_node(children[5])
        orelse_stmts = []
        if len(children) > 6:
            orelse_stmts = self.handle_node(children[-1])
        return ast.For(target, iter_expr, body_stmts, orelse_stmts,
                       lineno=location[0], col_offset=location[1])

    def handle_fpdef (self, node):
        children = node[1]
        if len(children) == 1:
            child_data = children[0][0]
            location = child_data[2]
            ret_val = ast.Name(child_data[1], self.expr_context(),
                               lineno=location[0], col_offset=location[1])
        else:
            assert len(children) == 3 and children[0][0][1] == "("
            ret_val = self.handle_node(children[1])
        return ret_val

    def handle_fplist (self, node):
        children = node[1]
        if len(children) == 1:
            ret_val = self.handle_node(children[0])
        else:
            old_context = self.expr_context
            self.expr_context = ast.Store
            tup_elems = [self.handle_node(child) for child in children
                         if not self.is_token(child)]
            self.expr_context = old_context
            ret_val = ast.Tuple(tup_elems, ast.Store(),
                                lineno=location[0], col_offset=location[1])
        return child_results

    def handle_funcdef (self, node):
        children = node[1]
        location = self._get_location(children[0])
        index = 1
        decorators = []
        if not self.is_token(children[0]):
            index = 2
            decorators = self.handle_node(children[0])
        name = children[index][0][1]
        index += 1
        params = self.handle_node(children[index])
        index += 1
        returns = None
        if self.is_token(children[index]) and children[index][0][1] == '->':
            returns = self.handle_node(children[index + 1])
            index += 2
        index += 1
        body = self.handle_node(children[index])
        if "returns" in ast.FunctionDef._fields:
            ret_val = ast.FunctionDef(name, params, body, decorators,
                                      returns,
                                      lineno=location[0],
                                      col_offset=location[1])
        else:
            ret_val = ast.FunctionDef(name, params, body, decorators,
                                      lineno=location[0],
                                      col_offset=location[1])
        return ret_val

    def handle_gen_for (self, node):
        return self._handle_comp_for(node)

    def handle_gen_if (self, node):
        return self._handle_comp_if(node)

    handle_gen_iter = _handle_only_child

    def handle_global_stmt (self, node):
        children = node[1]
        location = children[0][0][2]
        global_names = [child[0][1] for child in children[1::2]]
        return ast.Global(global_names,
                          lineno=location[0], col_offset=location[1])

    def handle_if_stmt (self, node):
        children = node[1]
        location = children[0][0][2]
        test = self.handle_node(children[1])
        body_stmts = self.handle_node(children[3])
        orelse_stmts = []
        elifs = []
        child_index = 4
        while ((child_index < len(children)) and
               (children[child_index][0][1] == "elif")):
            # XXX Another questionable location source (I would have
            # used the elif token location...)
            elifs.append((self._get_location(children[child_index + 1]),
                          self.handle_node(children[child_index + 1]),
                          self.handle_node(children[child_index + 3])))
            child_index += 4
        if child_index < len(children):
            assert children[child_index][0][1] == "else"
            orelse_stmts = self.handle_node(children[child_index + 2])
        if len(elifs) > 0:
            elifs.reverse()
            for elif_location, elif_test, elif_body in elifs:
                orelse_stmts = [ast.If(elif_test, elif_body, orelse_stmts,
                                       lineno=elif_location[0],
                                       col_offset=elif_location[1])]
        return ast.If(test, body_stmts, orelse_stmts,
                      lineno=location[0], col_offset=location[1])

    def handle_import_as_name (self, node):
        children = node[1]
        name = children[0][0][1]
        as_name = None
        if len(children) > 1:
            # XXX Same 'as' weirdness as in handle_dotted_as_name()...
            assert len(children) == 3
            as_name = children[2][0][1]
        return ast.alias(name, as_name)

    handle_import_as_names = _handle_nontoken_children

    def handle_import_from (self, node):
        children = node[1]
        child_count = len(children)
        location = children[0][0][2]
        level = 0
        child_index = 1
        while ((child_index < child_count) and
               (self.is_token(children[child_index])) and
               (children[child_index][0][1] == ".")):
            level += 1
            child_index += 1
        module_name = ""
        if ((child_index < child_count) and
            (not self.is_token(children[child_index]))):
            module_name = "".join(token[1] for token in
                                  self._get_tokens(children[child_index]))
            child_index += 1
        assert ((child_index < child_count) and
                (children[child_index][0][1] == "import"))
        child_index += 1
        names = []
        if ((child_index < child_count) and
            (self.is_token(children[child_index]))):
            if children[child_index][0][1] == "*":
                names.append(ast.alias("*", None))
            else:
                assert children[child_index][0][1] == "("
                names = self.handle_node(children[child_index + 1])
        else:
            names = self.handle_node(children[child_index])
        return ast.ImportFrom(module_name, names, level,
                              lineno=location[0], col_offset=location[1])

    def handle_import_name (self, node):
        children = node[1]
        lineno, col_offset = children[0][0][2]
        return ast.Import(self.handle_node(children[1]),
                          lineno=lineno, col_offset=col_offset)

    handle_import_stmt = _handle_only_child

    def handle_lambdef (self, node):
        children = node[1]
        location = children[0][0][2]
        args = ast.arguments([], None, None, [])
        if len(children) > 3:
            args = self.handle_node(children[1])
        body = self.handle_node(children[-1])
        return ast.Lambda(args, body,
                          lineno=location[0], col_offset=location[1])

    def handle_lambdef_nocond (self, node):
        raise NotImplementedError()

    def handle_list_and_or_kw_args (self, node):
        children = node[1]
        vararg_name = None
        kwarg_name = None
        kw_index = 1
        if children[0][0][1] == "*":
            vararg_name = children[1][0][1]
            kw_index = 4
        if kw_index < len(children):
            kwarg_name = children[kw_index][0][1]
        return ([], vararg_name, kwarg_name, [])

    def handle_list_for (self, node):
        return self._handle_comp_for(node)

    def handle_list_if (self, node):
        return self._handle_comp_if(node)

    handle_list_iter = _handle_only_child

    def handle_listmaker (self, node):
        children = node[1]
        first_elem = self.handle_node(children[0])
        if len(children) == 1:
            ret_val = ast.List([first_elem], self.expr_context())
        else:
            if self.is_token(children[1]):
                # Comma separated list.
                child_elems = [first_elem] + [self.handle_node(child)
                                              for child in children[2::2]]
                ret_val = ast.List(child_elems, self.expr_context())
            else:
                # List comprehension
                location = self._get_location(children[0])
                comp_ifs, comprehensions = self.handle_node(children[1])
                assert len(comp_ifs) == 0
                # XXX Okay, this is just messed up.  I have to set the
                # position here, but must set it in the caller for
                # lists?!?
                ret_val = ast.ListComp(first_elem, comprehensions,
                              lineno=location[0], col_offset=location[1])
        return ret_val

    def handle_nonlocal_stmt (self, node):
        raise NotImplementedError()

    def handle_not_test (self, node):
        children = node[1]
        if len(children) > 1:
            assert len(children) == 2
            location = children[0][0][2]
            ret_val = ast.UnaryOp(ast.Not(), self.handle_node(children[1]),
                                  lineno=location[0], col_offset=location[1])
        else:
            ret_val = self.handle_node(children[0])
        return ret_val

    # This is groovy because old_lambdef and lambdef have the same
    # shape despite having different nonterminal contents.  This is
    # only reachable from list comprehensions anyway...
    handle_old_lambdef = handle_lambdef

    handle_old_test = _handle_only_child

    def handle_or_test (self, node):
        return self._handle_logical_op(node, ast.Or)

    def handle_parameters (self, node):
        children = node[1]
        if len(children) > 2:
            ret_val = self.handle_node(children[1])
        else:
            ret_val = ast.arguments([], None, None, [])
        return ret_val

    def handle_pass_stmt (self, node):
        children = node[1]
        assert len(children) == 1
        location = children[0][0][2]
        return ast.Pass(lineno=location[0], col_offset=location[1])

    def _process_trailer (self, value, trailer, location):
        ret_val = self.handle_node(trailer)
        if hasattr(ret_val, "value"):
            ret_val.value = value
        elif hasattr(ret_val, "func"):
            ret_val.func = value
        # XXX I'm not really happy about this position convention.
        ret_val.lineno = location[0]
        ret_val.col_offset = location[1]
        return ret_val

    def handle_power (self, node):
        children = node[1]
        if len(children) == 1:
            ret_val = self.handle_node(children[0])
        else:
            location = self._get_location(children[0])
            starstar_flag = self.is_token(children[-2])
            power_rhs = None
            if self.is_token(children[-2]):
                assert children[-2][0][1] == "**"
                power_rhs = children[-1]
                children = children[:-2]
            if len(children) == 1:
                ret_val = self.handle_node(children[0])
            else:
                old_context = self.expr_context
                self.expr_context = ast.Load
                crnt_val = self.handle_node(children[0])
                for child in children[1:-1]:
                    crnt_val = self._process_trailer(crnt_val, child, location)
                self.expr_context = old_context
                ret_val = self._process_trailer(crnt_val, children[-1],
                                                location)
            if power_rhs:
                ret_val = ast.BinOp(ret_val, ast.Pow(),
                                    self.handle_node(power_rhs),
                                    lineno=location[0], col_offset=location[1])
        return ret_val

    def handle_print_stmt (self, node):
        children = node[1]
        location = children[0][0][2]
        children = children[1:]
        dest = None
        values = []
        newline = True
        if children:
            if self.is_token(children[0]) and children[0][0][1] == ">>":
                dest = self.handle_node(children[1])
                children = children[2:]
            values = [self.handle_node(child) for child in children
                      if not self.is_token(child)]
            if children:
                newline = not (self.is_token(children[-1]) and
                               children[-1][0][1] == ",")
        return ast.Print(dest, values, newline,
                         lineno=location[0], col_offset=location[1])

    def handle_raise_stmt (self, node):
        children = node[1]
        child_count = len(children)
        location = children[0][0][2]
        exn_type = None
        exn_inst = None
        exn_tback = None
        if child_count > 1:
            exn_type = self.handle_node(children[1])
            if child_count > 3:
                exn_inst = self.handle_node(children[3])
                if child_count > 5:
                    exn_tback = self.handle_node(children[5])
        return ast.Raise(exn_type, exn_inst, exn_tback,
                         lineno=location[0], col_offset=location[1])

    def handle_return_stmt (self, node):
        children = node[1]
        location = children[0][0][2]
        value = None
        if len(children) > 1:
            value = self.handle_node(children[1])
        return ast.Return(value, lineno=location[0], col_offset=location[1])

    def handle_shift_expr (self, node):
        def shift_op (tok):
            return ast.LShift() if tok[1] == "<<" else ast.RShift()
        return self._handle_left_binop(node, shift_op)

    handle_simple_stmt = _handle_nontoken_children

    def handle_single_input (self, node):
        child_results = self.handle_children(node)
        return child_results

    def handle_sliceop (self, node):
        children = node[1]
        if len(children) == 1:
            # XXX Is this right?  This is what the Python compiler returns...
            location = self._get_location(children[0])
            ret_val = ast.Name("None", ast.Load(),
                               lineno=location[0], col_offset=location[1])
        else:
            ret_val = self.handle_node(children[1])
        return ret_val

    handle_small_stmt = _handle_only_child

    def handle_star_expr (self, node):
        raise NotImplementedError()

    handle_start = _handle_only_child

    handle_stmt = _handle_only_child

    def handle_subscript (self, node):
        children = node[1]
        if len(children) == 1:
            # XXX Would really like to hand up an Index() instance,
            # but unfortunately, handle_subscriptlist() must be able
            # to determine if the index is a tuple and not an extended
            # slice.
            if self.is_token(children[0]):
                assert children[0][0][1] == ":"
                ret_val = ast.Slice(None, None, None)
            else:
                ret_val = self.handle_node(children[0])
        elif ((len(children) == 3) and
              self.is_token(children[0]) and
              (children[0][0][1] == ".")):
            ret_val = ast.Ellipsis()
        else:
            lower = None
            upper = None
            step = None
            child_index = 0
            if not self.is_token(children[child_index]):
                lower = self.handle_node(children[child_index])
                child_index += 1
            assert (self.is_token(children[child_index]) and
                    children[child_index][0][1] == ":")
            child_index += 1
            # XXX Would like better way of determining what kind of
            # nonterminal a node is...
            if ((child_index < len(children)) and
                (children[child_index][0] == "test")):
                upper = self.handle_node(children[child_index])
                child_index += 1
            if child_index < len(children):
                step = self.handle_node(children[child_index])
            ret_val = ast.Slice(lower, upper, step)
        return ret_val

    def _is_slice_type (self, obj):
        return type(obj) in (ast.Ellipsis, ast.Slice, ast.ExtSlice, ast.Index)

    def handle_subscriptlist (self, node):
        children = node[1]
        if len(children) == 1:
            ret_val = self.handle_node(children[0])
        else:
            child_elems = [self.handle_node(child) for child in children
                           if not self.is_token(child)]
            is_slice = False
            for child in child_elems:
                if self._is_slice_type(child):
                    is_slice = True
                    break
            if is_slice:
                child_elems = [child_elem
                               if self._is_slice_type(child_elem) else
                               ast.Index(child_elem)
                               for child_elem in child_elems]
                ret_val = ast.ExtSlice(child_elems)
            else:
                location = self._get_location(children[0])
                ret_val = ast.Tuple(child_elems, self.expr_context(),
                                    lineno=location[0], col_offset=location[1])
        if not self._is_slice_type(ret_val):
            ret_val = ast.Index(ret_val)
        return ret_val

    def handle_suite (self, node):
        return self._flatten_once(self._handle_nontoken_children(node))

    def handle_term (self, node):
        def term_op (tok):
            return {"*" : ast.Mult,
                    "/" : ast.Div,
                    "%" : ast.Mod,
                    "//" : ast.FloorDiv}[tok[1]]()
        return self._handle_left_binop(node, term_op)

    def handle_test (self, node):
        children = node[1]
        if len(children) == 1:
            ret_val = self.handle_node(children[0])
        else:
            lineno, col_offset = self._get_location(children[0])
            true_expr = self.handle_node(children[0])
            pred_expr = self.handle_node(children[2])
            false_expr = self.handle_node(children[4])
            ret_val = ast.IfExp(pred_expr, true_expr, false_expr,
                                lineno=lineno, col_offset=col_offset)
        return ret_val

    def handle_test_nocond (self, node):
        raise NotImplementedError()

    def handle_testlist (self, node):
        children = node[1]
        if len(children) == 1:
            ret_val = self.handle_node(children[0])
        else:
            lineno, col_offset = self._get_location(children[0])
            tup_elems = self._handle_nontoken_children(node)
            ret_val = ast.Tuple(tup_elems, self.expr_context(),
                                lineno=lineno, col_offset=col_offset)
        return ret_val

    handle_testlist1 = handle_testlist

    def handle_testlist_comp (self, node):
        return self.handle_testlist_gexp(node)

    def handle_testlist_gexp (self, node):
        children = node[1]
        ret_val = self.handle_node(children[0])
        if len(children) > 1:
            lineno, col_offset = self._get_location(children[0])
            if self.is_token(children[1]):
                # Tuple
                tuple_elems = [ret_val] + [self.handle_node(child)
                                           for child in children[2:]
                                           if not self.is_token(child)]
                ret_val = ast.Tuple(tuple_elems, self.expr_context(),
                                    lineno=lineno, col_offset=col_offset)
            else:
                # Generator
                assert len(children) == 2
                if_exprs, comprehensions = self.handle_node(children[1])
                assert len(if_exprs) == 0
                ret_val = ast.GeneratorExp(
                    ret_val, comprehensions,
                    lineno=lineno, col_offset=col_offset)
        return ret_val

    # This is cool, since testlist_safe and testlist still have the same shape.
    handle_testlist_safe = handle_testlist

    # This is also cool, since testlist_star_expr and testlist still
    # have the same shape...though star_expr will crash...
    handle_testlist_star_expr = handle_testlist

    def handle_tfpdef (self, node):
        children = node[1]
        arg = children[0][0][1]
        annotation = (None if len(children) < 2
                      else self.handle_node(children[-1]))
        return ast.arg(arg, annotation)

    def handle_trailer (self, node):
        children = node[1]
        assert self.is_token(children[0])
        token_data = children[0][0]
        token_text = token_data[1]
        lineno, col_offset = token_data[2]
        if token_text == "(":
            call_args = [[], [], None, None]
            if len(children) == 3:
                call_args = self.handle_node(children[1])
            ret_val = ast.Call(None, *call_args)
        elif token_text == "[":
            old_context = self.expr_context
            self.expr_context = ast.Load
            child_slice = self.handle_node(children[1])
            self.expr_context = old_context
            ret_val = ast.Subscript(None, child_slice, self.expr_context(),
                                    lineno=lineno, col_offset=col_offset)
        elif token_text == ".":
            ret_val = ast.Attribute(None, children[1][0][1],
                                    self.expr_context(),
                                    lineno=lineno, col_offset=col_offset)
        return ret_val

    def handle_try_stmt (self, node):
        children = node[1]
        location = children[0][0][2]
        if self.is_token(children[3]):
            body_stmts = self.handle_node(children[2])
            final_stmts = self.handle_node(children[-1])
            ret_val = ast.TryFinally(
                body_stmts, final_stmts, lineno=location[0],
                col_offset=location[1])
        else:
            child_count = len(children)
            body_stmts = self.handle_node(children[2])
            handlers = []
            child_index = 3
            while ((child_index < child_count) and
                   (not self.is_token(children[child_index]))):
                except_location = self._get_location(children[child_index])
                except_results = self.handle_node(children[child_index])
                except_type = None
                if len(except_results) > 0:
                    except_type = except_results[0]
                except_name = None
                if len(except_results) > 1:
                    except_name = except_results[1]
                except_body = self.handle_node(children[child_index + 2])
                handlers.append(
                    ast.excepthandler(except_type, except_name,
                                      except_body, lineno=except_location[0],
                                      col_offset=except_location[1]))
                child_index += 3
            orelse_stmts = []
            if ((child_index < child_count) and
                self.is_token(children[child_index]) and
                (children[child_index][0][1] == "else")):
                orelse_stmts = self.handle_node(children[child_index + 2])
                child_index += 3
            ret_val = ast.TryExcept(body_stmts, handlers, orelse_stmts,
                                    lineno=location[0], col_offset=location[1])
            if ((child_index < child_count) and
                self.is_token(children[child_index]) and
                (children[child_index][0][1] == "finally")):
                finally_stmts = self.handle_node(children[child_index + 2])
                ret_val = ast.TryFinally(
                    [ret_val], finally_stmts,
                    lineno=location[0], col_offset=location[1])
        return ret_val

    def handle_typedargslist (self, node):
        return ast.arguments(*self._handle_arguments(node[1]))

    def _handle_varargs (self, children):
        # TODO: This currently handles both a modified varargslist (in
        # myfront.pgen), and the Python 2.6 varargslist (kinda).  Fix
        # it to only support the Python grammar once the deprecated
        # parser is removed.
        first_is_token = self.is_token(children[0])
        if not first_is_token and children[0][0] == "fpdef":
            old_context = self.expr_context
            self.expr_context = ast.Param
            fpdef_result = [self.handle_fpdef(children[0])]
            self.expr_context = old_context
            default_value = []
            tail_result = None
            if len(children) > 1:
                tail_index = 1
                while (tail_index < len(children) and
                       self.is_token(children[tail_index])):
                    if children[tail_index][0][1] == "=":
                        default_value = [self.handle_node(children[2])]
                        tail_index = 3
                    elif children[tail_index][0][1] == ",":
                        tail_index += 1
                    elif children[tail_index][0][1] in ("*", "**"):
                        break
                if tail_index < len(children):
                    if ((children[tail_index][0] == "fpdef") or
                        (self.is_token(children[tail_index]) and
                         (children[tail_index][0][1] in ("*", "**")))):
                        tail_result = self._handle_varargs(
                            children[tail_index:])
                    else:
                        tail_result = self.handle_node(children[tail_index])
            if tail_result is None:
                arg_args = (fpdef_result, None, None, default_value)
            else:
                if (len(default_value) > 0 and
                    (len(tail_result[3]) < len(tail_result[0]))):
                    # XXX
                    raise SyntaxError("non-default argument follows default "
                                      "argument")
                arg_args = (fpdef_result + tail_result[0],
                            tail_result[1], tail_result[2],
                            default_value + tail_result[3])
        elif first_is_token and self.is_token(children[1]):
            # XXX Synthesizing a deprecated parse tree node here.  See
            # TODO, above.
            arg_args = self.handle_node(('list_and_or_kw_args', children))
        elif (children[0][0] in ('tfpdef', 'vfpdef') or first_is_token):
            arg_args = self._handle_arguments(children)
        else:
            # Should be list_and_or_kw_args...
            assert len(children) == 1
            arg_args = self.handle_node(children[0])
        return arg_args

    def _handle_arguments (self, children):
        """Handle Python 3 concrete syntax that is used in the
        construction of the ast.arguments abstract syntax node.
        Returns the arguments to the ast.arguments constructor."""
        args, defaults, children = self._handle_arguments_head(children)
        (vararg, varargannotation, kwonlyargs, kwarg, kwargannotation,
         kw_defaults) = self._handle_arguments_tail(children)
        if len(ast.arguments._fields) == 8:
            return (args, vararg, varargannotation, kwonlyargs, kwarg,
                    kwargannotation, defaults, kw_defaults)
        return (args, vararg, kwonlyargs, kw_defaults, kwarg, defaults)
            

    def _handle_arguments_head (self, children):
        """Iterate through concrete syntax of the form:

        Xfpdef ['=' test] (',' Xfpdef ['=' test])* [',']

        Where Xfpdef is either tfpdef or vfpdef.  Returns a list of
        ast.arg instances, a list of AST nodes representing default
        values, and any remaining children."""
        args = []
        defaults = []
        index = 0
        child_count = len(children)
        while index < child_count:
            if self.is_token(children[index]):
                # Technically this makes it recognize (','*) instead
                # of ',', but the parser shouldn't allow that...
                if children[index][0][1] == ',':
                    index += 1
                    continue
                else:
                    break
            args.append(self.handle_node(children[index]))
            index += 1
            if index < child_count:
                assert self.is_token(children[index])
                if children[index][0][1] == '=':
                    index += 1
                    defaults.append(self.handle_node(children[index]))
                    index += 1
        return args, defaults, children[index:]

    def _handle_arguments_tail (self, children):
        """Iterate through concrete syntax of the form:

        '*' [Xfpdef] (',' Xfpdef ['=' test])* [',' '**' Xfpdef] | '**' Xfpdef
        """
        vararg = None
        varargannotation = None
        kwonlyargs = []
        kw_defaults = []
        kwarg = None
        kwargannotation = None
        if len(children) > 0:
            raise NotImplementedError(repr(children))
        return (vararg, varargannotation, kwonlyargs, kwarg, kwargannotation,
                kw_defaults)

    def handle_varargslist (self, node):
        children = node[1]
        arg_args = self._handle_varargs(children)
        return ast.arguments(*arg_args)

    def handle_varargslist_end (self, node):
        children = node[1]
        if len(children) == 1:
            ret_val = ([], None, None, [])
        else:
            ret_val = self._handle_varargs(children[1:])
        return ret_val

    def handle_vfpdef (self, node):
        assert len(node[1]) == 1
        return self.handle_tfpdef(node)

    def handle_while_stmt (self, node):
        children = node[1]
        location = children[0][0][2]
        test_expr = self.handle_node(children[1])
        body_stmts = self.handle_node(children[3])
        orelse_stmts = []
        if len(children) > 4:
            orelse_stmts = self.handle_node(children[-1])
        return ast.While(test_expr, body_stmts, orelse_stmts,
                         lineno=location[0], col_offset=location[1])

    def handle_with_item (self, node):
        children = node[1]
        context_expr = self.handle_node(children[0])
        optional_vars = None
        if len(children) != 1:
            assert len(children) == 3 and children[1][0][1] == 'as'
            old_context = self.expr_context
            self.expr_context = ast.Store
            optional_vars = self.handle_node(children[2])
            self.expr_context = old_context
        return context_expr, optional_vars

    def handle_with_stmt (self, node):
        children = node[1]
        location = children[0][0][2]
        if children[1][0] == 'test':
            context_expr = self.handle_node(children[1])
            optional_vars = None
            if not self.is_token(children[2]):
                optional_vars = self.handle_node(children[2])
        elif len(children) == 4:
            assert children[1][0] == 'with_item'
            context_expr, optional_vars = self.handle_node(children[1])
        else:
            # FIXME: Update this to handle multiple with_item children.
            raise NotImplementedError(repr(node))
        body_stmts = self.handle_node(children[-1])
        return ast.With(context_expr, optional_vars, body_stmts,
                        lineno=location[0], col_offset=location[1])

    def handle_with_var (self, node):
        # XXX Not sure this is correct; the with statement doesn't
        # compile w/o future import.  (Need to read the PEP.)
        children = node[1]
        assert len(children) == 2
        old_context = self.expr_context
        self.expr_context = ast.Store
        ret_val = self.handle_node(children[1])
        self.expr_context = old_context
        return ret_val

    def handle_xor_expr (self, node):
        return self._handle_left_binop(node, lambda x : ast.BitXor())

    def handle_yield_expr (self, node):
        children = node[1]
        location = children[0][0][2]
        value = None
        if len(children) > 1:
            value = self.handle_node(children[1])
        return ast.Yield(value, lineno=location[0], col_offset=location[1])

    def handle_yield_stmt (self, node):
        children = node[1]
        assert len(children) == 1
        child_result = self.handle_node(children[0])
        return ast.Expr(child_result, lineno=child_result.lineno,
                        col_offset=child_result.col_offset)

# ______________________________________________________________________
# Main (test) routine

def main(*args):
    from mython.myparser import MyParser
    import dis
    parser = MyParser()
    abstractor = MyHandler()
    for arg in args:
        print("\n".join(("_" * 70, arg, "_" * 60)))
        ast_obj = abstractor.handle_node(parser.parse_file(arg))
        print(ast.dump(ast_obj))
        ast.fix_missing_locations(ast_obj)
        co = compile(ast_obj, arg, 'exec', dont_inherit=True)
        dis.dis(co)
        print("_" * 70)

# ______________________________________________________________________

if __name__ == "__main__":
    import sys
    main(*sys.argv[1:])

# ______________________________________________________________________
# End of astify.py
