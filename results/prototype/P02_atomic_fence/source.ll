; ModuleID = '/home/zhovy/work/Case_Regression_Internal/cases/P02_atomic_fence/case.c'
source_filename = "/home/zhovy/work/Case_Regression_Internal/cases/P02_atomic_fence/case.c"
target datalayout = "e-m:e-p270:32:32-p271:32:32-p272:64:64-i64:64-i128:128-f80:128-n8:16:32:64-S128"
target triple = "x86_64-pc-linux-gnu"

@x = dso_local global i32 0, align 4, !dbg !0
@y = dso_local global i32 0, align 4, !dbg !16

; Function Attrs: noinline nounwind optnone uwtable
define dso_local ptr @writer(ptr noundef %0) #0 !dbg !29 {
  %2 = alloca ptr, align 8
  %3 = alloca i32, align 4
  %4 = alloca i32, align 4
  %5 = alloca i32, align 4
  store ptr %0, ptr %2, align 8
  call void @llvm.dbg.declare(metadata ptr %2, metadata !34, metadata !DIExpression()), !dbg !35
  %6 = load ptr, ptr %2, align 8, !dbg !36
  store i32 1, ptr %3, align 4, !dbg !37
  %7 = load i32, ptr %3, align 4, !dbg !37
  store atomic i32 %7, ptr @x monotonic, align 4, !dbg !37
  fence seq_cst, !dbg !38
  call void @llvm.dbg.declare(metadata ptr %4, metadata !39, metadata !DIExpression()), !dbg !40
  %8 = load atomic i32, ptr @y monotonic, align 4, !dbg !41
  store i32 %8, ptr %5, align 4, !dbg !41
  %9 = load i32, ptr %5, align 4, !dbg !41
  store i32 %9, ptr %4, align 4, !dbg !40
  %10 = load i32, ptr %4, align 4, !dbg !42
  ret ptr null, !dbg !43
}

; Function Attrs: nocallback nofree nosync nounwind speculatable willreturn memory(none)
declare void @llvm.dbg.declare(metadata, metadata, metadata) #1

; Function Attrs: noinline nounwind optnone uwtable
define dso_local ptr @reader(ptr noundef %0) #0 !dbg !44 {
  %2 = alloca ptr, align 8
  %3 = alloca i32, align 4
  %4 = alloca i32, align 4
  %5 = alloca i32, align 4
  store ptr %0, ptr %2, align 8
  call void @llvm.dbg.declare(metadata ptr %2, metadata !45, metadata !DIExpression()), !dbg !46
  %6 = load ptr, ptr %2, align 8, !dbg !47
  store i32 1, ptr %3, align 4, !dbg !48
  %7 = load i32, ptr %3, align 4, !dbg !48
  store atomic i32 %7, ptr @y monotonic, align 4, !dbg !48
  fence seq_cst, !dbg !49
  call void @llvm.dbg.declare(metadata ptr %4, metadata !50, metadata !DIExpression()), !dbg !51
  %8 = load atomic i32, ptr @x monotonic, align 4, !dbg !52
  store i32 %8, ptr %5, align 4, !dbg !52
  %9 = load i32, ptr %5, align 4, !dbg !52
  store i32 %9, ptr %4, align 4, !dbg !51
  %10 = load i32, ptr %4, align 4, !dbg !53
  ret ptr null, !dbg !54
}

; Function Attrs: noinline nounwind optnone uwtable
define dso_local i32 @main() #0 !dbg !55 {
  %1 = alloca i32, align 4
  %2 = alloca i64, align 8
  %3 = alloca i64, align 8
  store i32 0, ptr %1, align 4
  call void @llvm.dbg.declare(metadata ptr %2, metadata !58, metadata !DIExpression()), !dbg !62
  call void @llvm.dbg.declare(metadata ptr %3, metadata !63, metadata !DIExpression()), !dbg !64
  %4 = call i32 @pthread_create(ptr noundef %2, ptr noundef null, ptr noundef @writer, ptr noundef null) #4, !dbg !65
  %5 = call i32 @pthread_create(ptr noundef %3, ptr noundef null, ptr noundef @reader, ptr noundef null) #4, !dbg !66
  %6 = load i64, ptr %2, align 8, !dbg !67
  %7 = call i32 @pthread_join(i64 noundef %6, ptr noundef null), !dbg !68
  %8 = load i64, ptr %3, align 8, !dbg !69
  %9 = call i32 @pthread_join(i64 noundef %8, ptr noundef null), !dbg !70
  ret i32 0, !dbg !71
}

; Function Attrs: nounwind
declare i32 @pthread_create(ptr noundef, ptr noundef, ptr noundef, ptr noundef) #2

declare i32 @pthread_join(i64 noundef, ptr noundef) #3

attributes #0 = { noinline nounwind optnone uwtable "frame-pointer"="all" "min-legal-vector-width"="0" "no-trapping-math"="true" "stack-protector-buffer-size"="8" "target-cpu"="x86-64" "target-features"="+cmov,+cx8,+fxsr,+mmx,+sse,+sse2,+x87" "tune-cpu"="generic" }
attributes #1 = { nocallback nofree nosync nounwind speculatable willreturn memory(none) }
attributes #2 = { nounwind "frame-pointer"="all" "no-trapping-math"="true" "stack-protector-buffer-size"="8" "target-cpu"="x86-64" "target-features"="+cmov,+cx8,+fxsr,+mmx,+sse,+sse2,+x87" "tune-cpu"="generic" }
attributes #3 = { "frame-pointer"="all" "no-trapping-math"="true" "stack-protector-buffer-size"="8" "target-cpu"="x86-64" "target-features"="+cmov,+cx8,+fxsr,+mmx,+sse,+sse2,+x87" "tune-cpu"="generic" }
attributes #4 = { nounwind }

!llvm.dbg.cu = !{!2}
!llvm.module.flags = !{!21, !22, !23, !24, !25, !26, !27}
!llvm.ident = !{!28}

!0 = !DIGlobalVariableExpression(var: !1, expr: !DIExpression())
!1 = distinct !DIGlobalVariable(name: "x", scope: !2, file: !18, line: 4, type: !19, isLocal: false, isDefinition: true)
!2 = distinct !DICompileUnit(language: DW_LANG_C11, file: !3, producer: "Ubuntu clang version 18.1.3 (1ubuntu1)", isOptimized: false, runtimeVersion: 0, emissionKind: FullDebug, enums: !4, globals: !15, splitDebugInlining: false, nameTableKind: None)
!3 = !DIFile(filename: "/home/zhovy/work/Case_Regression_Internal/cases/P02_atomic_fence/case.c", directory: "/home/zhovy/work/Case_Regression_Internal", checksumkind: CSK_MD5, checksum: "9e6d62cec7f3302a9d6cc8629f68ab95")
!4 = !{!5}
!5 = !DICompositeType(tag: DW_TAG_enumeration_type, name: "memory_order", file: !6, line: 65, baseType: !7, size: 32, elements: !8)
!6 = !DIFile(filename: ".tools/clang18/usr/lib/llvm-18/lib/clang/18/include/stdatomic.h", directory: "/home/zhovy/work", checksumkind: CSK_MD5, checksum: "1c2aee2a953dfc5407753d1f439b6977")
!7 = !DIBasicType(name: "unsigned int", size: 32, encoding: DW_ATE_unsigned)
!8 = !{!9, !10, !11, !12, !13, !14}
!9 = !DIEnumerator(name: "memory_order_relaxed", value: 0)
!10 = !DIEnumerator(name: "memory_order_consume", value: 1)
!11 = !DIEnumerator(name: "memory_order_acquire", value: 2)
!12 = !DIEnumerator(name: "memory_order_release", value: 3)
!13 = !DIEnumerator(name: "memory_order_acq_rel", value: 4)
!14 = !DIEnumerator(name: "memory_order_seq_cst", value: 5)
!15 = !{!0, !16}
!16 = !DIGlobalVariableExpression(var: !17, expr: !DIExpression())
!17 = distinct !DIGlobalVariable(name: "y", scope: !2, file: !18, line: 5, type: !19, isLocal: false, isDefinition: true)
!18 = !DIFile(filename: "cases/P02_atomic_fence/case.c", directory: "/home/zhovy/work/Case_Regression_Internal", checksumkind: CSK_MD5, checksum: "9e6d62cec7f3302a9d6cc8629f68ab95")
!19 = !DIDerivedType(tag: DW_TAG_atomic_type, baseType: !20)
!20 = !DIBasicType(name: "int", size: 32, encoding: DW_ATE_signed)
!21 = !{i32 7, !"Dwarf Version", i32 5}
!22 = !{i32 2, !"Debug Info Version", i32 3}
!23 = !{i32 1, !"wchar_size", i32 4}
!24 = !{i32 8, !"PIC Level", i32 2}
!25 = !{i32 7, !"PIE Level", i32 2}
!26 = !{i32 7, !"uwtable", i32 2}
!27 = !{i32 7, !"frame-pointer", i32 2}
!28 = !{!"Ubuntu clang version 18.1.3 (1ubuntu1)"}
!29 = distinct !DISubprogram(name: "writer", scope: !18, file: !18, line: 7, type: !30, scopeLine: 7, flags: DIFlagPrototyped, spFlags: DISPFlagDefinition, unit: !2, retainedNodes: !33)
!30 = !DISubroutineType(types: !31)
!31 = !{!32, !32}
!32 = !DIDerivedType(tag: DW_TAG_pointer_type, baseType: null, size: 64)
!33 = !{}
!34 = !DILocalVariable(name: "arg", arg: 1, scope: !29, file: !18, line: 7, type: !32)
!35 = !DILocation(line: 7, column: 20, scope: !29)
!36 = !DILocation(line: 8, column: 11, scope: !29)
!37 = !DILocation(line: 9, column: 5, scope: !29)
!38 = !DILocation(line: 10, column: 5, scope: !29)
!39 = !DILocalVariable(name: "r0", scope: !29, file: !18, line: 11, type: !20)
!40 = !DILocation(line: 11, column: 9, scope: !29)
!41 = !DILocation(line: 11, column: 14, scope: !29)
!42 = !DILocation(line: 12, column: 11, scope: !29)
!43 = !DILocation(line: 13, column: 5, scope: !29)
!44 = distinct !DISubprogram(name: "reader", scope: !18, file: !18, line: 16, type: !30, scopeLine: 16, flags: DIFlagPrototyped, spFlags: DISPFlagDefinition, unit: !2, retainedNodes: !33)
!45 = !DILocalVariable(name: "arg", arg: 1, scope: !44, file: !18, line: 16, type: !32)
!46 = !DILocation(line: 16, column: 20, scope: !44)
!47 = !DILocation(line: 17, column: 11, scope: !44)
!48 = !DILocation(line: 18, column: 5, scope: !44)
!49 = !DILocation(line: 19, column: 5, scope: !44)
!50 = !DILocalVariable(name: "r1", scope: !44, file: !18, line: 20, type: !20)
!51 = !DILocation(line: 20, column: 9, scope: !44)
!52 = !DILocation(line: 20, column: 14, scope: !44)
!53 = !DILocation(line: 21, column: 11, scope: !44)
!54 = !DILocation(line: 22, column: 5, scope: !44)
!55 = distinct !DISubprogram(name: "main", scope: !18, file: !18, line: 25, type: !56, scopeLine: 25, flags: DIFlagPrototyped, spFlags: DISPFlagDefinition, unit: !2, retainedNodes: !33)
!56 = !DISubroutineType(types: !57)
!57 = !{!20}
!58 = !DILocalVariable(name: "first", scope: !55, file: !18, line: 26, type: !59)
!59 = !DIDerivedType(tag: DW_TAG_typedef, name: "pthread_t", file: !60, line: 27, baseType: !61)
!60 = !DIFile(filename: "/usr/include/x86_64-linux-gnu/bits/pthreadtypes.h", directory: "", checksumkind: CSK_MD5, checksum: "8a5acdbeec491eca11cf81cb1ef77ea7")
!61 = !DIBasicType(name: "unsigned long", size: 64, encoding: DW_ATE_unsigned)
!62 = !DILocation(line: 26, column: 15, scope: !55)
!63 = !DILocalVariable(name: "second", scope: !55, file: !18, line: 26, type: !59)
!64 = !DILocation(line: 26, column: 22, scope: !55)
!65 = !DILocation(line: 27, column: 5, scope: !55)
!66 = !DILocation(line: 28, column: 5, scope: !55)
!67 = !DILocation(line: 29, column: 18, scope: !55)
!68 = !DILocation(line: 29, column: 5, scope: !55)
!69 = !DILocation(line: 30, column: 18, scope: !55)
!70 = !DILocation(line: 30, column: 5, scope: !55)
!71 = !DILocation(line: 31, column: 5, scope: !55)
