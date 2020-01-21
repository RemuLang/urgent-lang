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

可以`match`的很多, 但所有特性打算在variant type做了之后再写.
还是extensible pattern matching(之后可以自定义模式匹配规则), 表达力换exhaustive checking.


## Open, Import

项目根目录那个`prelude.ugt`可以拿来试, 打开`ugt repl`,
```shell script
Urgent> import Pre
Urgent> do print 1
Undef print
Urgent> let x = Pre
Urgent> do x.print 1
1
Urgent> open x
Urgent> print 1
1
```

`import`导入模块但不加载它的成员, `open`加载成员.
看起来似乎是python的`import <mod>`和`from <mod> import *`, 其实不是.

一切都是静态的, 只有module可以被import和open. `x`之所以可以被open,
是因为`x`被分析为是模块`Pre`的alias.

Urgent是pure的, 变量不可以多次赋值(只有绑定), 所以, 上面代码里任何使用`x`的地方都会索引到模块`Pre`.

如果说`python import *`是有运行时开销的, 那么, 已经加载过的模块在urgent里,
无论在哪儿open都是0开销的.

一种来自于ML语言的用法是, 在局部打开模块.
```shell script
Urgent> import Pre
Urgent> let x = 1
Urgent> do print 1
Undef print

Urgent> let x = let y = 2 open Pre in print 1
1
Urgent> do print 1
Undef print
```   

## 语句引导的表达式

`open`, `let`, `rec`, `def`这些语句后面可以跟一个`in`, 表示表达式.
```shell script
Urgent> let x = def x = 1 in open Pre in print <| x + 1
2
```

连续的`let`, `open`, 这些语句, 可以不写`in`.

```shell script
Urgent> let x = let x = 1 let y = 2 let c = 3 open Pre in print <| x + y + c
6
Urgent> do print <| 1 + 2 + 3
Undef operator.<|
Urgent> do print (1+2)
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
do x match
  1 or 2 or 3 => 0,
  x and (y, z) => (y, x, z) 
```


## WIP的特性

- variants
```shell script
Nil ()
Cons(_, _)

let print_lst = lst ->
  lst match
    Nil         => ...,
    Cons (a, b) =>  ...
```

## WIP的其他东西

标准库, 

`ref`类型.

```shell script
let a = ref 0
do a := 1
do a := (1, 2)
```


例如`for`函数和`while`函数之类的.

```shell script
let x = ref 0
for { deref x  < 10 } {
   do x := deref x + 1
   do print <| deref x
   ()
}   
```

造一些方便度比list comprehension好的玩意儿.

还可以弄一些糖, 比如单目运算符.

打算把`{ ... }`做成空参数lambda, 但是觉得有点浪费大括号.
