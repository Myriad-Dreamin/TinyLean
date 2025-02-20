from dataclasses import dataclass, field
from functools import reduce as _r
from typing import Optional, cast as _c, OrderedDict
from collections import OrderedDict as _Od

from . import Name, Param, Def, Data as DataDecl, Ctor as CtorDecl


@dataclass(frozen=True)
class IR: ...


@dataclass(frozen=True)
class Type(IR):
    def __str__(self):
        return "Type"


@dataclass(frozen=True)
class Ref(IR):
    name: Name

    def __str__(self):
        return str(self.name)


@dataclass(frozen=True)
class FnType(IR):
    param: Param[IR]
    ret: IR

    def __str__(self):
        return f"{self.param} → {self.ret}"


@dataclass(frozen=True)
class Fn(IR):
    param: Param[IR]
    body: IR

    def __str__(self):
        return f"λ {self.param} ↦ {self.body}"


@dataclass(frozen=True)
class Call(IR):
    callee: IR
    arg: IR

    def __str__(self):
        return f"({self.callee} {self.arg})"


@dataclass(frozen=True)
class Placeholder(IR):
    id: int
    is_user: bool

    def __str__(self):
        t = "u" if self.is_user else "m"
        return f"?{t}.{self.id}"


@dataclass(frozen=True)
class Data(IR):
    name: Name
    args: OrderedDict[int, IR]

    def __str__(self):
        s = " ".join(str(x) for x in [self.name, *self.args.values()])
        return f"({s})" if len(self.args) else s


@dataclass(frozen=True)
class Ctor(IR):
    ty_name: Name
    name: Name
    args: OrderedDict[int, IR]

    def __str__(self):
        n = f"{self.ty_name}.{self.name}"
        s = " ".join(str(x) for x in [n, *self.args.values()])
        return f"({s})" if len(self.args) else s


@dataclass(frozen=True)
class Nomatch(IR):
    def __str__(self):
        return "nomatch"


# TODO: Testing.
@dataclass(frozen=True)
class Case(IR):  # pragma: no cover
    ctor: Name
    params: list[Param[IR]]
    body: IR

    def __str__(self):
        s = " ".join([str(self.ctor), *map(str, self.params)])
        return f"| {s} => {self.body}"


# TODO: Testing.
@dataclass(frozen=True)
class Match(IR):  # pragma: no cover
    arg: IR
    cases: dict[int, Case]

    def __str__(self):
        cs = " ".join(map(str, self.cases.values()))
        return f"match {self.arg} with {cs}"


@dataclass(frozen=True)
class Renamer:
    locals: dict[int, int] = field(default_factory=dict)

    def run(self, v: IR) -> IR:
        if isinstance(v, Ref):
            if v.name.id in self.locals:
                return Ref(Name(v.name.text, self.locals[v.name.id]))
            return v
        if isinstance(v, Call):
            return Call(self.run(v.callee), self.run(v.arg))
        if isinstance(v, Fn):
            return Fn(self._param(v.param), self.run(v.body))
        if isinstance(v, FnType):
            return FnType(self._param(v.param), self.run(v.ret))
        if isinstance(v, Data):
            return Data(v.name, _Od({i: self.run(v) for i, v in v.args.items()}))
        if isinstance(v, Ctor):
            args = _Od({i: self.run(v) for i, v in v.args.items()})
            return Ctor(v.ty_name, v.name, args)
        if isinstance(v, Match):
            arg = self.run(v.arg)
            cases = {
                i: Case(c.ctor, [self._param(p) for p in c.params], self.run(c.body))
                for i, c in v.cases.items()
            }
            return Match(arg, cases)
        # assert any(isinstance(v, c) for c in (Type, Placeholder, Nomatch))
        any(isinstance(v, c) for c in (Type, Placeholder, Nomatch))
        return v

    def _param(self, p: Param[IR]):
        name = Name(p.name.text)
        self.locals[p.name.id] = name.id
        return Param(name, self.run(p.type), p.is_implicit)


_rn = lambda v: Renamer().run(v)


def _to(p: list[Param[IR]], v: IR, t=False):
    return _r(lambda a, q: _c(IR, FnType(q, a) if t else Fn(q, a)), reversed(p), v)


def from_def(d: Def[IR]):
    return _rn(_to(d.params, d.body)), _rn(_to(d.params, d.ret, True))


def from_data(d: DataDecl[IR]):
    args = _Od({p.name.id: Ref(p.name) for p in d.params})
    return _rn(_to(d.params, Data(d.name, args))), _rn(_to(d.params, Type(), True))


def from_ctor(c: CtorDecl[IR], d: DataDecl[IR]):
    adhoc = _c(list[tuple[Ref, IR]], c.ty_args)
    adhoc_xs = {x.name.id for x, _ in adhoc}
    miss = [Param(p.name, p.type, True) for p in d.params if p.name.id not in adhoc_xs]

    args = _Od({p.name.id: Ref(p.name) for p in c.params})
    v = _to(c.params, Ctor(d.name, c.name, args))
    v = _to(miss, v)

    ty_miss_args = _Od({p.name.id: Ref(p.name) for p in miss})
    ty_adhoc_args = _Od({x.name.id: v for x, v in adhoc})
    ty = _to(c.params, Data(d.name, ty_miss_args | ty_adhoc_args), True)
    ty = _to(miss, ty, True)

    return _rn(v), _rn(ty)


@dataclass
class Answer:
    type: IR
    value: Optional[IR] = None

    def is_unsolved(self):
        return self.value is None


@dataclass(frozen=True)
class Hole:
    loc: int
    is_user: bool
    locals: dict[int, Param[IR]]
    answer: Answer


@dataclass(frozen=True)
class Inliner:
    holes: OrderedDict[int, Hole]
    env: dict[int, IR] = field(default_factory=dict)

    def run(self, v: IR) -> IR:
        if isinstance(v, Ref):
            return self.run(_rn(self.env[v.name.id])) if v.name.id in self.env else v
        if isinstance(v, Call):
            f = self.run(v.callee)
            x = self.run(v.arg)
            if isinstance(f, Fn):
                return self.run_with(f.body, (f.param.name, x))
            return Call(f, x)
        if isinstance(v, Fn):
            return Fn(self._param(v.param), self.run(v.body))
        if isinstance(v, FnType):
            return FnType(self._param(v.param), self.run(v.ret))
        if isinstance(v, Placeholder):
            h = self.holes[v.id]
            h.answer.type = self.run(h.answer.type)
            return v if h.answer.is_unsolved() else self.run(h.answer.value)
        if isinstance(v, Ctor):
            args = _Od({i: self.run(v) for i, v in v.args.items()})
            return Ctor(v.ty_name, v.name, args)
        if isinstance(v, Data):
            return Data(v.name, _Od({i: self.run(v) for i, v in v.args.items()}))
        if isinstance(v, Match):
            arg = self.run(v.arg)
            cases = {
                i: Case(c.ctor, [self._param(p) for p in c.params], self.run(c.body))
                for i, c in v.cases.items()
            }
            if not isinstance(arg, Ctor):  # pragma: no cover
                # TODO: Testing.
                return Match(arg, cases)
            c = cases[arg.name.id]
            env = [(x.name, v) for x, v in zip(c.params, arg.args.values())]
            return self.run_with(c.body, *env)
        assert isinstance(v, Type) or isinstance(v, Nomatch)
        return v

    def run_with(self, x: IR, *env: tuple[Name, IR]):
        self.env.update({n.id: v for n, v in env})
        return self.run(x)

    def apply(self, f: IR, *args: IR):
        ret = f
        for x in args:
            if isinstance(ret, Fn):
                ret = self.run_with(ret.body, (ret.param.name, x))
            else:
                ret = Call(ret, x)
        return ret

    def _param(self, p: Param[IR]):
        return Param(p.name, self.run(p.type), p.is_implicit)


@dataclass(frozen=True)
class Converter:
    holes: OrderedDict[int, Hole]

    def eq(self, lhs: IR, rhs: IR):
        match lhs, rhs:
            case Placeholder() as x, y:
                return self._solve(x, y)
            case x, Placeholder() as y:
                return self._solve(y, x)
            case Ref(x), Ref(y):
                return x.id == y.id
            case Call(f, x), Call(g, y):
                return self.eq(f, g) and self.eq(x, y)
            case FnType(p, b), FnType(q, c):
                if not self.eq(p.type, q.type):
                    return False
                env = (q.name, Ref(p.name))
                return self.eq(b, Inliner(self.holes).run_with(c, env))
            case Data(x, xs), Data(y, ys):
                return x.id == y.id and self._args(xs, ys)
            case Ctor(t, x, xs), Ctor(u, y, ys):
                return t.id == u.id and x.id == y.id and self._args(xs, ys)
            case (Type(), Type()) | (Nomatch(), Nomatch()):
                return True

        # FIXME: Following cases not seen in tests yet:
        assert not (isinstance(lhs, Fn) and isinstance(rhs, Fn))
        assert not (isinstance(lhs, Placeholder) and isinstance(rhs, Placeholder))
        assert not (isinstance(lhs, Match) and isinstance(rhs, Match))

        return False

    def _solve(self, p: Placeholder, answer: IR):
        h = self.holes[p.id]
        assert h.answer.is_unsolved()  # FIXME: can be not None here?
        h.answer.value = answer

        if isinstance(answer, Ref):
            for param in h.locals.values():
                if param.name.id == answer.name.id:
                    assert self.eq(param.type, h.answer.type)  # FIXME: will fail here?

        return True

    def _args(self, xs: dict[int, IR], ys: dict[int, IR]):
        assert len(xs) == len(ys)
        for i, a in xs.items():
            if not self.eq(a, ys[i]):
                return False
        return True
