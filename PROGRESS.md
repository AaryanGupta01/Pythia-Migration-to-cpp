# PYTHIA Project Progress

## Project Overview

PYTHIA is a source-to-source compiler for a statically typed subset of Python, called PySub. The project translates supported Python programs into generated native code and preserves Python-like behavior through a runtime library and semantic checks.

The project began as a Python-subset-to-C11 transpiler. It has since been migrated so that the generated code is emitted and built as C++17.

```text
PySub source (.py)
        |
        v
Lexer -> Parser/AST -> Type checker -> Lowering -> C++ emitter
                                                     |
                                                     v
                                             Generated .cpp file
                                                     |
                                                     v
                                            C++17 compiler + runtime
```

## Work Completed

### Vishal Vivek

Vishal Vivek developed the original front end and the initial Python-to-C transpilation path. His work included:

- Defining the supported PySub subset and grammar.
- Implementing lexical analysis, including indentation and dedentation handling.
- Implementing parsing and AST construction.
- Connecting the compiler pipeline from Python source through type checking and lowering.
- Producing the initial C11-based transpilation workflow.

The original implementation generated C code from supported Python-subset programs and used the C runtime and compiler toolchain to build executable output.

### Aaryan Gupta

Aaryan Gupta migrated the generated-code target from C11 to C++17. This work included:

- Adapting the code-generation stage from C output to C++ output.
- Updating generated file handling to use `.cpp` output files.
- Updating the build command to compile generated code with `c++ -std=c++17`.
- Migrating the runtime integration from the C runtime interface to the C++ runtime files.
- Preserving the existing compiler pipeline and Python-subset behavior while changing the target language.
- Maintaining the differential-testing and build/run workflow for generated programs.

The current command-line driver can emit generated C++, build it, and run it. For example:

```bash
python3 -m pythia.cli tests/positive/t07_bubble.py --emit-only
python3 -m pythia.cli tests/positive/t07_bubble.py --run
```

## Dictionary Library Work

### Rujuta Kulkarni and Jahnavi Koliparthy

Rujuta Kulkarni and Jahnavi Koliparthy worked on adding dictionary-library support to the project. Their work was intended to extend the supported Python subset and provide the required dictionary data structures and operations for generated programs.

- Defining the dictionary representation used by generated code.
- Implementing dictionary operations required by the supported Python subset.
- Connecting dictionary operations to the compiler/runtime pipeline.
- Considering how dictionaries interact with type checking, lowering, code generation, and the target runtime.

## Challenges in Adding the Dictionary Library

### 1. Input format

The first challenge is determining exactly where dictionary code and dictionary functions enter the compiler pipeline, and in what format they are received.

Questions include:

- Does dictionary syntax enter through the lexer and parser as normal Python-subset syntax?
- Does the type checker receive a dedicated dictionary type and typed dictionary operations?
- Does the lowering stage convert dictionaries into an intermediate representation before code generation?
- Are dictionary helper functions provided as source-level functions, compiler-generated operations, or runtime-library functions?

A clear input contract is needed so the dictionary implementation matches the existing AST, typed representation, and lowering stages.

### 2. Output format

The second challenge is defining the format that dictionary support must produce for the next stage.

Questions include:

- What representation should the lowering pass produce?
- What C++ types and helper functions should the emitter generate?
- Which dictionary operations should become inline generated code, and which should call runtime functions?
- How should errors such as missing keys be represented and reported?

The output contract must be compatible with the current C++17 emitter and the C++ runtime interface.

### 3. Referencing external libraries

The third challenge is determining where and how external dictionary libraries or helper implementations should be referenced by the current code.

Questions include:

- Should dictionary support be implemented in the project runtime, or linked as a separate library?
- Which generated headers need to be included in the output?
- How will the build command locate and compile the dictionary implementation?
- How can the generated program remain reproducible across supported environments?

The integration should follow the existing runtime pattern so generated programs have an explicit and reliable dependency path.

## Current Status

- The original Python-subset-to-C11 transpilation work is complete.
- The generated-code target has been migrated from C11 to C++17.
- The command-line workflow supports emitting, building, and running generated C++ programs.
- The existing tests and runtime provide a baseline for validating the migration.
- Dictionary-library work by Rujuta Kulkarni and Jahnavi Koliparthy has been undertaken, but it is not yet present and verified in this working copy.
- The next integration step is to pull the dictionary changes, resolve the input/output/runtime contracts, and run the complete positive and negative test suites.

## Team Summary

| Contributor | Main contribution | 
|---|---|
| Vishal Vivek | Python-subset front end and original Python-to-C11 transpilation path |
| Aaryan Gupta | Migration of generated output and runtime build flow from C11 to C++17 |
| Rujuta Kulkarni | Dictionary-library support work and related compiler/type-system considerations 
| Jahnavi Koliparthy | Dictionary-library support work and related runtime/integration considerations |
