from pathlib import Path
from typing import cast
from unittest import TestCase

from . import parse
from .. import ast, Name, grammar, Param, Decl, ir


class TestIdent(TestCase):
    def test_fresh(self):
        self.assertNotEqual(Name("i").id, Name("j").id)


class TestParser(TestCase):
    def test_parse_name(self):
        x = parse(grammar.name, "  hello")[0]
        assert isinstance(x, Name)
        self.assertEqual("hello", x.text)

    def test_parse_name_unbound(self):
        x = parse(grammar.name, "_")[0]
        self.assertTrue(x.is_unbound())

    def test_parse_type(self):
        x = parse(grammar.type_, "  Type")[0]
        assert isinstance(x, ast.Type)
        self.assertEqual(2, x.loc)

    def test_parse_reference(self):
        x = parse(grammar.ref, "  hello")[0]
        assert isinstance(x, ast.Ref)
        self.assertEqual(2, x.loc)
        self.assertEqual("hello", x.name.text)

    def test_parse_paren_expr(self):
        x = parse(grammar.p_expr, "(hello)")[0]
        assert isinstance(x, ast.Ref)
        self.assertEqual(1, x.loc)
        self.assertEqual("hello", x.name.text)

    def test_parse_implicit_param(self):
        x = parse(grammar.implicit_param, " {a: b}")[0]
        assert isinstance(x, Param)
        self.assertTrue(x.implicit)
        self.assertEqual("a", x.name.text)
        assert isinstance(x.type, ast.Ref)
        self.assertEqual(5, x.type.loc)

    def test_parse_explicit_param(self):
        x = parse(grammar.explicit_param, " (a : Type)")[0]
        assert isinstance(x, Param)
        self.assertFalse(x.implicit)
        self.assertEqual("a", x.name.text)
        assert isinstance(x.type, ast.Type)
        self.assertEqual(6, x.type.loc)

    def test_parse_call(self):
        x = parse(grammar.call, "a b")[0]
        assert isinstance(x, ast.Call)
        self.assertEqual(0, x.loc)
        assert isinstance(x.callee, ast.Ref)
        self.assertEqual(0, x.callee.loc)
        self.assertEqual("a", x.callee.name.text)
        self.assertEqual(2, x.arg.loc)
        assert isinstance(x.arg, ast.Ref)
        self.assertEqual("b", x.arg.name.text)

    def test_parse_call_paren(self):
        x = parse(grammar.call, "(a) b (Type)")[0]
        assert isinstance(x, ast.Call)
        self.assertEqual(0, x.loc)
        assert isinstance(x.callee, ast.Call)
        assert isinstance(x.callee.callee, ast.Ref)
        self.assertEqual(1, x.callee.callee.loc)
        self.assertEqual("a", x.callee.callee.name.text)
        assert isinstance(x.callee.arg, ast.Ref)
        self.assertEqual(4, x.callee.arg.loc)
        self.assertEqual("b", x.callee.arg.name.text)
        assert isinstance(x.arg, ast.Type)
        self.assertEqual(7, x.arg.loc)

    def test_parse_call_paren_function(self):
        x = parse(grammar.call, "(fun _ => Type) Type")[0]
        assert isinstance(x, ast.Call)
        self.assertEqual(0, x.loc)
        assert isinstance(x.callee, ast.Fn)
        self.assertEqual(1, x.callee.loc)
        self.assertTrue(x.callee.param.is_unbound())
        assert isinstance(x.callee.body, ast.Type)
        self.assertEqual(10, x.callee.body.loc)
        assert isinstance(x.arg, ast.Type)
        self.assertEqual(16, x.arg.loc)

    def test_parse_function_type(self):
        x = parse(grammar.fn_type, "  (a : Type) -> a")[0]
        assert isinstance(x, ast.FnType)
        assert isinstance(x.param, Param)
        self.assertEqual("a", x.param.name.text)
        assert isinstance(x.param.type, ast.Type)
        self.assertEqual(7, x.param.type.loc)
        assert isinstance(x.ret, ast.Ref)
        self.assertEqual("a", x.ret.name.text)
        self.assertEqual(16, x.ret.loc)

    def test_parse_function_type_long(self):
        x = parse(grammar.fn_type, " {a : Type} -> (b: Type) -> a")[0]
        assert isinstance(x, ast.FnType)
        assert isinstance(x.param, Param)
        self.assertEqual("a", x.param.name.text)
        assert isinstance(x.param.type, ast.Type)
        self.assertEqual(6, x.param.type.loc)
        assert isinstance(x.ret, ast.FnType)
        assert isinstance(x.ret.param, Param)
        self.assertEqual("b", x.ret.param.name.text)
        assert isinstance(x.ret.param.type, ast.Type)
        self.assertEqual(19, x.ret.param.type.loc)
        assert isinstance(x.ret.ret, ast.Ref)
        self.assertEqual("a", x.ret.ret.name.text)
        self.assertEqual(28, x.ret.ret.loc)

    def test_parse_function(self):
        x = parse(grammar.fn, "  fun a => a")[0]
        assert isinstance(x, ast.Fn)
        self.assertEqual(2, x.loc)
        assert isinstance(x.param, Name)
        self.assertEqual("a", x.param.text)
        assert isinstance(x.body, ast.Ref)
        self.assertEqual("a", x.body.name.text)
        self.assertEqual(11, x.body.loc)

    def test_parse_function_long(self):
        x = parse(grammar.fn, "   fun a => fun b => a b")[0]
        assert isinstance(x, ast.Fn)
        self.assertEqual(3, x.loc)
        assert isinstance(x.param, Name)
        self.assertEqual("a", x.param.text)
        assert isinstance(x.body, ast.Fn)
        self.assertEqual(12, x.body.loc)
        assert isinstance(x.body.param, Name)
        self.assertEqual("b", x.body.param.text)
        assert isinstance(x.body.body, ast.Call)
        self.assertEqual(21, x.body.body.loc)
        assert isinstance(x.body.body.callee, ast.Ref)
        self.assertEqual("a", x.body.body.callee.name.text)
        assert isinstance(x.body.body.arg, ast.Ref)
        self.assertEqual("b", x.body.body.arg.name.text)

    def test_parse_function_multi(self):
        x = parse(grammar.fn, "  fun c d => c d")[0]
        assert isinstance(x, ast.Fn)
        self.assertEqual(2, x.loc)
        assert isinstance(x.param, Name)
        self.assertEqual("c", x.param.text)
        assert isinstance(x.body, ast.Fn)
        self.assertEqual(2, x.body.loc)
        assert isinstance(x.body.param, Name)
        self.assertEqual("d", x.body.param.text)

    def test_parse_definition_constant(self):
        x = parse(grammar.definition, "  def f : Type := Type")[0]
        assert isinstance(x, Decl)
        self.assertEqual(6, x.loc)
        self.assertEqual("f", x.name.text)
        self.assertEqual(0, len(x.params))
        assert isinstance(x.ret, ast.Type)
        self.assertEqual(10, x.ret.loc)
        assert isinstance(x.body, ast.Type)
        self.assertEqual(18, x.body.loc)

    def test_parse_definition(self):
        x = parse(grammar.definition, "  def f {a: Type} (b: Type): Type := a")[0]
        assert isinstance(x, Decl)
        self.assertEqual(6, x.loc)
        self.assertEqual("f", x.name.text)
        assert isinstance(x.params, list)
        self.assertEqual(2, len(x.params))
        assert isinstance(x.params[0], ast.Param)
        self.assertTrue(x.params[0].implicit)
        self.assertEqual("a", x.params[0].name.text)
        assert isinstance(x.params[0].type, ast.Type)
        self.assertEqual(12, x.params[0].type.loc)
        assert isinstance(x.params[1], ast.Param)
        self.assertFalse(x.params[1].implicit)
        self.assertEqual("b", x.params[1].name.text)
        assert isinstance(x.params[1].type, ast.Type)
        self.assertEqual(22, x.params[1].type.loc)

    def test_parse_program(self):
        x = list(
            parse(
                grammar.program,
                """
                def a: Type := Type
                def b: Type := Type
                """,
            )
        )
        self.assertEqual(2, len(x))
        assert isinstance(x[0], Decl)
        self.assertEqual("a", x[0].name.text)
        assert isinstance(x[1], Decl)
        self.assertEqual("b", x[1].name.text)

    def test_parse_example(self):
        x = parse(grammar.example, "  example: Type := Type")[0]
        assert isinstance(x, Decl)
        self.assertEqual(2, x.loc)
        self.assertTrue(x.name.is_unbound())
        self.assertEqual(0, len(x.params))
        assert isinstance(x.ret, ast.Type)
        assert isinstance(x.body, ast.Type)

    def test_parse_placeholder(self):
        x = parse(grammar.fn, " fun _ => _")[0]
        assert isinstance(x, ast.Fn)
        self.assertTrue(x.param.is_unbound())
        assert isinstance(x.body, ast.Placeholder)
        self.assertEqual(10, x.body.loc)

    def test_parse_return_type(self):
        x = parse(grammar.return_type, ": Type")[0]
        assert isinstance(x, ast.Type)
        self.assertEqual(2, x.loc)

    def test_parse_return_placeholder(self):
        x = parse(grammar.return_type, "")[0]
        assert isinstance(x, ast.Placeholder)
        self.assertFalse(x.is_user)

    def test_parse_definition_no_return(self):
        x = parse(grammar.definition, "def a := Type")[0]
        assert isinstance(x.ret, ast.Placeholder)
        self.assertFalse(x.ret.is_user)

    def test_parse_call_implicit(self):
        x = parse(grammar.call, "a (T:=Nat)")[0]
        assert isinstance(x, ast.Call)
        assert isinstance(x.callee, ast.Ref)
        self.assertEqual("a", x.callee.name.text)
        assert isinstance(x.implicit_to, str)
        self.assertEqual("T", x.implicit_to)
        assert isinstance(x.arg, ast.Ref)
        self.assertEqual("Nat", x.arg.name.text)


resolve = lambda s: s | ast.Parser() | ast.NameResolver()
resolve_md = lambda s: s | ast.Parser(True) | ast.NameResolver()
resolve_expr = lambda s: ast.NameResolver().expr(parse(grammar.expr, s)[0])


class TestNameResolver(TestCase):
    def test_resolve_expr_function(self):
        x = cast(ast.Fn, resolve_expr("fun a => fun b => a b"))
        y = cast(ast.Fn, x.body)
        z = cast(ast.Call, y.body)
        callee = cast(ast.Ref, z.callee)
        arg = cast(ast.Ref, z.arg)
        self.assertEqual(x.param.id, callee.name.id)
        self.assertEqual(y.param.id, arg.name.id)

    def test_resolve_expr_function_shadowed(self):
        x = cast(ast.Fn, resolve_expr("fun a => fun a => a"))
        y = cast(ast.Fn, x.body)
        z = cast(ast.Ref, y.body)
        self.assertNotEqual(x.param.id, z.name.id)
        self.assertEqual(y.param.id, z.name.id)

    def test_resolve_expr_function_failed(self):
        with self.assertRaises(ast.UndefinedVariableError) as e:
            resolve_expr("fun a => b")
        n, loc = e.exception.args
        self.assertEqual(9, loc)
        self.assertEqual("b", n.text)

    def test_resolve_expr_function_type(self):
        x = cast(ast.FnType, resolve_expr("{a: Type} -> (b: Type) -> a"))
        y = cast(ast.FnType, x.ret)
        z = cast(ast.Ref, y.ret)
        self.assertEqual(x.param.name.id, z.name.id)
        self.assertNotEqual(y.param.name.id, z.name.id)

    def test_resolve_expr_function_type_failed(self):
        with self.assertRaises(ast.UndefinedVariableError) as e:
            resolve_expr("{a: Type} -> (b: Type) -> c")
        n, loc = e.exception.args
        self.assertEqual(26, loc)
        self.assertEqual("c", n.text)

    def test_resolve_program(self):
        resolve(
            """
            def f0 (a: Type): Type := a
            def f1 (a: Type): Type := f0 a 
            """
        )

    def test_resolve_program_failed(self):
        with self.assertRaises(ast.UndefinedVariableError) as e:
            resolve("def f (a: Type) (b: c): Type := Type")
        n, loc = e.exception.args
        self.assertEqual(20, loc)
        self.assertEqual("c", n.text)

    def test_resolve_program_duplicate(self):
        with self.assertRaises(ast.DuplicateVariableError) as e:
            resolve(
                """
                def f0: Type := Type
                def f0: Type := Type
                """
            )
        n, loc = e.exception.args
        self.assertEqual(58, loc)
        self.assertEqual("f0", n.text)

    def test_resolve_expr_placeholder(self):
        resolve_expr("{a: Type} -> (b: Type) -> _")


check_expr = lambda s, t: ast.TypeChecker().check(resolve_expr(s), t)
infer_expr = lambda s: ast.TypeChecker().infer(resolve_expr(s))


class TestTypeChecker(TestCase):
    def test_check_expr_type(self):
        check_expr("Type", ir.Type())
        check_expr("{a: Type} -> (b: Type) -> a", ir.Type())

    def test_check_expr_type_failed(self):
        with self.assertRaises(ast.TypeMismatchError) as e:
            check_expr("fun a => a", ir.Type())
        want, got, loc = e.exception.args
        self.assertEqual(0, loc)
        self.assertEqual("Type", want)
        self.assertEqual("function", got)

    def test_check_expr_function(self):
        check_expr(
            "fun a => a",
            ir.FnType(Param(Name("a"), ir.Type(), False), ir.Type()),
        )

    def test_check_expr_on_infer(self):
        check_expr("Type", ir.Type())

    def test_check_expr_on_infer_failed(self):
        with self.assertRaises(ast.TypeMismatchError) as e:
            check_expr("(a: Type) -> a", ir.Ref(Name("a")))
        want, got, loc = e.exception.args
        self.assertEqual(0, loc)
        self.assertEqual("a", want)
        self.assertEqual("Type", got)

    def test_infer_expr_type(self):
        v, ty = infer_expr("Type")
        assert isinstance(v, ir.Type)
        assert isinstance(ty, ir.Type)

    def test_infer_expr_call_failed(self):
        with self.assertRaises(ast.TypeMismatchError) as e:
            infer_expr("(Type) Type")
        want, got, loc = e.exception.args
        self.assertEqual(1, loc)
        self.assertEqual("function", want)
        self.assertEqual("Type", got)

    def test_infer_expr_function_type(self):
        v, ty = infer_expr("{a: Type} -> a")
        assert isinstance(v, ir.FnType)
        self.assertEqual("{a: Type} → a", str(v))
        assert isinstance(ty, ir.Type)

    def test_check_program(self):
        ast.check_string("def a: Type := Type")
        ast.check_string("def f (a: Type): Type := a")
        ast.check_string("def f: (_: Type) -> Type := fun a => a")
        ast.check_string("def id (T: Type) (a: T): T := a")

    def test_check_program_failed(self):
        with self.assertRaises(ast.TypeMismatchError) as e:
            ast.check_string("def id (a: Type): a := Type")
        want, got, loc = e.exception.args
        self.assertEqual(23, loc)
        self.assertEqual("a", str(want))
        self.assertEqual("Type", str(got))

    def test_check_program_call(self):
        ast.check_string(
            """
            def f0 (a: Type): Type := a
            def f1: Type := f0 Type
            def f2: f0 Type := Type
            """
        )

    def test_check_program_call_failed(self):
        with self.assertRaises(ast.TypeMismatchError) as e:
            ast.check_string(
                """
                def f0 (a: Type): Type := a
                def f1 (a: Type): Type := f0
                """
            )
        want, got, loc = e.exception.args
        self.assertEqual(87, loc)
        self.assertEqual("Type", str(want))
        self.assertEqual("(a: Type) → Type", str(got))

    def test_check_program_placeholder(self):
        ast.check_string(
            """
            def a := Type
            def b: Type := a
            """
        )

    def test_check_program_placeholder_locals(self):
        ast.check_string("def f (T: Type) (a: T) := a")

    def test_check_program_placeholder_unsolved(self):
        with self.assertRaises(ast.UnsolvedPlaceholderError) as e:
            ast.check_string("def a: Type := _")
        name, ctx, ty, loc = e.exception.args
        self.assertTrue(name.startswith("?u"))
        self.assertEqual(0, len(ctx))
        assert isinstance(ty, ir.Type)
        self.assertEqual(15, loc)


def nat_to_int(v: ir.IR):
    n = 0
    while True:
        if isinstance(v, ir.Fn):
            v = v.body
        else:
            break
    while True:
        if isinstance(v, ir.Call):
            assert isinstance(v.callee, ir.Ref)
            assert v.callee.name.text == "S"
            v = v.arg
            n += 1
        else:
            assert isinstance(v, ir.Ref)
            assert v.name.text == "Z"
            break
    return n


class TestTheoremProving(TestCase):
    def test_nat(self):
        _, _, _, _3, _6, _9 = ast.check_string(
            """
            def Nat: Type :=
                (T: Type) -> (S: (n: T) -> T) -> (Z: T) -> T

            def add (a: Nat) (b: Nat): Nat :=
                fun T S Z => (a T S) (b T S Z)

            def mul (a: Nat) (b: Nat): Nat :=
                fun T S Z => (a T) (b T S) Z

            def _3: Nat := fun T S Z => S (S (S Z))

            def _6: Nat := add _3 _3

            def _9: Nat := mul _3 _3
            """
        )
        self.assertEqual(3, nat_to_int(_3.body))
        self.assertEqual(6, nat_to_int(_6.body))
        self.assertEqual(9, nat_to_int(_9.body))

    def test_leibniz_equality(self):
        ast.check_string(
            """
            def Eq (T: Type) (a: T) (b: T): Type :=
                (p: (v: T) -> Type) -> (pa: p a) -> p b

            def refl (T: Type) (a: T): Eq T a a :=
                fun p pa => pa

            def sym (T: Type) (a: T) (b: T) (p: Eq T a b): Eq T b a :=
                (p (fun b => Eq T b a)) (refl T a)

            def A: Type := Type

            def B: Type := Type

            def lemma: Eq Type A B := refl Type A

            def theorem (p: Eq Type A B): Eq Type B A := sym Type A B lemma
            """
        )

    def test_leibniz_equality_failed(self):
        with self.assertRaises(ast.TypeMismatchError) as e:
            ast.check_string(
                """
                def Eq (T: Type) (a: T) (b: T): Type := (p: (v: T) -> Type) -> (pa: p a) -> p b
                def refl (T: Type) (a: T): Eq T a a := fun p => fun pa => pa
                def A: Type := (a: Type) -> Type
                def B: Type := (a: (b: Type) -> Type) -> Type
                def _: Eq Type A B := refl Type A
                /-                    ^~~^ failed here -/
                """
            )
        want, got, loc = e.exception.args
        self.assertEqual(323, loc)
        self.assertEqual(
            "(p: (v: Type) → Type) → (pa: (p (a: Type) → Type)) → (p (a: (b: Type) → Type) → Type)",
            str(want),
        )
        self.assertEqual(
            "(p: (v: Type) → Type) → (pa: (p (a: Type) → Type)) → (p (a: Type) → Type)",
            str(got),
        )

    def test_markdown(self):
        results = ast.check_string(
            """\
# Heading 1

```lean
def Eq (T: Type) (a: T) (b: T): Type := (p: (v: T) -> Type) -> (pa: p a) -> p b

def refl (T: Type) (a: T): Eq T a a := fun p => fun pa => pa
```

```lean
def sym (T: Type) (a: T) (b: T) (p: Eq T a b): Eq T b a := (p (fun b => Eq T b a)) (refl T a)
```

```lean4
def A: Type := Type
```

```python
print("Hello, world!")
```

```
Broken code.
```````

Footer.
            """,
            True,
        )
        self.assertEqual(3, len(results))
        eq, refl, sym = results
        self.assertEqual("Eq", eq.name.text)
        self.assertEqual("refl", refl.name.text)
        self.assertEqual("sym", sym.name.text)

    def test_readme(self):
        p = Path(__file__).parent / ".." / ".." / ".." / ".github" / "README.md"
        with open(p) as f:
            results = ast.check_string(f.read(), True)
        self.assertGreater(len(results), 1)

    def test_example(self):
        ast.check_string(
            """
            def T: Type := Type
            example: Type := T
            """
        )
