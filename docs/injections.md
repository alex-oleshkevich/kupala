# Dependency Injection

Kupala's IoC container can invoke callables or instantiate classes resolving and injecting their dependencies. When you
tell the container to invoke a callable it will inspect function signature and will look up for registered services.

> All arguments must be annotated otherwise `InjectionError` will be raised. But there is an option to work around it. See below.

## Invoking a callable

To invoke a callable call `Container.invoke` method and pass a function to it:

```python
def some_function(service: ServiceType) -> str:
    print('invoked!')


container.invoke(some_function)  # receives instance of "ServiceType" and prints 'invoked!'
```

## Instantiating a class

In the same way, you can create class instances using `invoke` function. If class has parents then their `__init__`
arguments will be inspected and added to the injection plan.

```python
class MyClass:
    def __init__(service: ServiceType) -> None:
        ...


instance = container.invoke(MyClass)
```

## Passing additional arguments

If function/class has arguments that are not registered in the container the `InjectionError` will be raised. You can
provide injector with values for these arguments via `extra_kwargs`. The injector will use it instead of querying the
container.

```python
def some_function(service: ServiceType, var_a: int, var_b: str) -> str:
    ...


container.invoke(some_function, extra_kwargs={'var_a': 'value a', 'var_b': 'value b'})
```

