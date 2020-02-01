# 很急语言, 一个"过渡"语言.

安装pip, 命令ugt

(`pip install urgent`, `ugt --help`)

运行3.6, 编译3.7

(3.7, 3.8上, urgent编译出的字节码可以被3.6加载, 也就是没有使用ROT4和LOAD_METHOD这些新的指令)


跨版本加载用`--raw_bytecode` flag.

```shell script
ugt cc <xxx.ugt> <xxx.code> -- raw_bytecode --project bootstrap.toml
```
后,
```
import marshal
code_object = marshal.load(open("xxx.code", 'rb'))
exec(code_object, globals())
```

## 语句(伪)

- `let/def`和`rec`.

```
let x = 1
def x = 1
```
一个意思.

- `rec`
```
rec f = x -> (f, x)
```
是递归, 也就是自己的定义中可以出现自己.


- `let ..., ... `

```
let x = 1, y = 2, z = ...,
```

定义时`x, y, z`互不引用, 他们定义时用到的`x, y, z`来自外部.
 

- `rec ..., ...`.

```
rec x = a -> (a, y), y = a -> (a, x) , z = ...,
```

定义时, `x, y, z`互相引用.


## If

```
<expr> ?
    <expr>
else
    <expr>
```

我觉得语法还行.

```shell script
how?
  fine
else
  emmm  
```

还阔以.

## Match

```shell script
let x  =
(1, 2) match
  (a, b, c) => a,
  (1, 2) => 0
```

可以`match`的很多, 更多例子见后面的variants.

注意, 二元运算符会被当作解构器.

我们还支持view pattern.

```shell script
let f = x -> (x, 2 * x)

1 match (f -> (a, b)) => a + b # 1 + 2 * 1 
5 match (f -> (a, b)) => a + b # 5 + 2 * 5 
```

## Open, Import

项目根目录那个`hello.ugt`可以拿来试, 打开`ugt repl`,
```shell script
Urgent> import Hello
Urgent> print 1
Undef print
Urgent> let x = Hello
Urgent> x.print 1
1
Urgent> open x
Urgent> print 1
1
```

`import`导入模块但不加载它的成员, `open`加载成员.
看起来似乎是python的`import <mod>`和`from <mod> import *`, 其实不是.

一切都是静态的, 只有module可以被import和open. `x`之所以可以被open,
是因为`x`被分析为是模块`Hello`的alias.

Urgent是pure的, 变量不可以多次赋值(只有绑定), 所以, 上面代码里任何使用`x`的地方都会索引到模块`Hello`.

如果说`python import *`是有运行时开销的, 那么, 已经加载过的模块在urgent里,
无论在哪儿open都是0开销的.

一种来自于ML语言的用法是, 在局部打开模块.
```shell script
Urgent> import Hello
Urgent> let x = 1
Urgent> print 1
Undef print

Urgent> let x = let y = 2 open Hello in print 1
1
Urgent> print 1
Undef print
```   

## 语句引导的表达式

`open`, `let`, `rec`, `def`这些语句后面可以跟一个`in`, 表示表达式.
```shell script
Urgent> let x = def x = 1 in open Hello in print <| x + 1
2
```

连续的`let`, `open`, 这些语句, 可以不写`in`.

```shell script
Urgent> let x = let x = 1 let y = 2 let c = 3 open Hello in print <| x + y + c
6
Urgent> print <| 1 + 2 + 3
Undef operator.<|
Urgent> print (1+2)
Undef operator.+
```

## 中缀定义

```shell script
infixl + 10
```

左结合，优先级10.

```shell script
infixr <| 0
```

右结合, 优先级0.

优先级是一个整数, 可以为负.

如果想要使用其他模块定义的运算符优先级和结合性, 可以open该模块.
如果不想污染作用域, 可以局部open该模块.

只有`and`和`or`两个是固定的优先级, 他们的优先级都比其他二元运算符低.

`and`和`or`也用在pattern matching中.
`and`表示左右俩都要match, `or`表示只match一个.

```shell script
x match
  1 or 2 or 3 => 0,
  x and (y, z) => (y, x, z) 
```


## Variants

```shell script
data Nil, Cons(_, _) 
infixr :: 1
let :: = Cons

let l1 = Cons 1 Nil

let print_lst = lst ->
  lst match
    1 :: Cons a b => ...,
    Cons a b => ...,
    Nil =>  ...
```

`[]`语法是`Nil`的简写, `[a, b]`这样的语法是`Cons a (Cons b Nil)`的简写, 所以我们可以

```shell script
data Nil, Cons(_, _) 
infixr :: 1
let :: = Cons
let l1 = [1]

let print_lst = lst ->
  lst match
    1 :: a :: b => ...,
    a :: b => ...,
    [] =>  ...
```

局部定义的variants:
```shell script
let x = data A, B, C in
  (A, B, C)
A

# Undef: A
```

这是用来动态create数据类型的. 注意这对于运行时来说比较缓慢. 一般来说, 还是把数据创建放到模块顶层. 

Variants的成员可以按名字访问:
```shell script
data Either(left, right)
let x = Either(1, 2)
x.left |> print
```

## 尾递归

urgent实现了尾递归, 所以, 你可以随意地写递归函数定义.

我们不能说这个速度非常快, 实际上, 比起python循环, 相同情况下我们的尾递归性能只有其一半,
更别说我们还有柯里化.

然而, 既然你在看了, 那我可以开心地向你保证, **这是Python世界最快的, 且货真价实的尾递归实现**.

其基本原理相当简单, 你可以在`codegen.py`的`preload`方法里找到一个用字节码书写的,
优化到极致的尾递归scheduler. 

我会在非尾递归调用点应用这个scheduler,
你能同通过阅读`compiler.py`的`v_tco`以及`v_call`方法, 来进一步理解尾递归优化的实现.

## Python函数调用

```shell script
f.(a, b, c)
```

像这样, 调用时加个点的函数, 就是按照Python的调用约定. 这并不和我们的尾递归优化冲突.

## Imperative Programming

下面的代码需要加载项目目录下的`base/prelude.ugt`.

- `ref`
```shell script
Urgent> let x = ref 1
=> ()
Urgent> x
=> ref 1
Urgent> x := 2
=> ()
Urgent> x
=> ref 2
Urgent> !x + 2
=> 4
```

- `for`

```shell script
Urgent> for [1, 2, 3] ( x -> 
  print x
)
1
2
3
=> ()
```

- `while`

```shell script
Urgent> let x = ref 1
=> ()
Urgent> while { !x < 10 } {
  do print !x
  in x := !x + 1
}

1
2
3
4
5
6
7
8
9
=> ()
```

上面的循环暂时是尾递归写的, 之后会用Python字节码重写.

`for`和`while`的实现如下:
```shell script
rec for = seq -> f ->
    seq match
        [] => (),
        hd :: tl =>
            do f hd
            in for tl f

rec while = cond -> f ->
    cond () ?
        do f ()
        in while cond f
    else ()
```

都可以良好地尾递归.

## 项目构建

urgent把所有代码编译成单个.pyc文件.


```shell script
# 编译
sh> ugt cc <主模块.ugt> <a.pyc> --project <项目文件.toml>
# 直接执行
sh> ugt run <主模块.ugt> --project <项目文件.toml>
# 启动REPL
sh> ugt repl --project <项目文件.toml>
```

一个示例的项目文件见`bootstrap.toml`.

packaging和project building这些方面其实还没设计好, 但先用着了. 做事第一.

## WIP: Traits
