; ModuleID = '/home/zhovy/work/Case_Regression_Internal/cases/P03_release_acquire_relay/case.c'
source_filename = "/home/zhovy/work/Case_Regression_Internal/cases/P03_release_acquire_relay/case.c"
target datalayout = "e-m:e-p270:32:32-p271:32:32-p272:64:64-i64:64-i128:128-f80:128-n8:16:32:64-S128"
target triple = "x86_64-pc-linux-gnu"

@data = dso_local global i32 0, align 4, !dbg !0
@flag = dso_local global i32 0, align 4, !dbg !16
@relay_flag = dso_local global i32 0, align 4, !dbg !21

; Function Attrs: noinline nounwind optnone uwtable
define dso_local ptr @writer(ptr noundef %0) #0 !dbg !31 {
  %2 = alloca ptr, align 8
  store ptr %0, ptr %2, align 8
  call void @llvm.dbg.declare(metadata ptr %2, metadata !36, metadata !DIExpression()), !dbg !37
  %3 = load ptr, ptr %2, align 8, !dbg !38
  call void @publish_data(), !dbg !39
  ret ptr null, !dbg !40
}

; Function Attrs: nocallback nofree nosync nounwind speculatable willreturn memory(none)
declare void @llvm.dbg.declare(metadata, metadata, metadata) #1

; Function Attrs: noinline nounwind optnone uwtable
define internal void @publish_data() #0 !dbg !41 {
  %1 = alloca i32, align 4
  %2 = alloca i32, align 4
  store i32 1, ptr %1, align 4, !dbg !44
  %3 = load i32, ptr %1, align 4, !dbg !44
  store atomic i32 %3, ptr @data monotonic, align 4, !dbg !44
  store i32 1, ptr %2, align 4, !dbg !45
  %4 = load i32, ptr %2, align 4, !dbg !45
  store atomic i32 %4, ptr @flag release, align 4, !dbg !45
  ret void, !dbg !46
}

; Function Attrs: noinline nounwind optnone uwtable
define dso_local ptr @relay(ptr noundef %0) #0 !dbg !47 {
  %2 = alloca ptr, align 8
  store ptr %0, ptr %2, align 8
  call void @llvm.dbg.declare(metadata ptr %2, metadata !48, metadata !DIExpression()), !dbg !49
  %3 = load ptr, ptr %2, align 8, !dbg !50
  call void @relay_once(), !dbg !51
  ret ptr null, !dbg !52
}

; Function Attrs: noinline nounwind optnone uwtable
define internal void @relay_once() #0 !dbg !53 {
  %1 = alloca i32, align 4
  %2 = alloca i32, align 4
  %3 = alloca i32, align 4
  call void @llvm.dbg.declare(metadata ptr %1, metadata !54, metadata !DIExpression()), !dbg !55
  %4 = load atomic i32, ptr @flag acquire, align 4, !dbg !56
  store i32 %4, ptr %2, align 4, !dbg !56
  %5 = load i32, ptr %2, align 4, !dbg !56
  store i32 %5, ptr %1, align 4, !dbg !55
  %6 = load i32, ptr %1, align 4, !dbg !57
  store i32 %6, ptr %3, align 4, !dbg !58
  %7 = load i32, ptr %3, align 4, !dbg !58
  store atomic i32 %7, ptr @relay_flag release, align 4, !dbg !58
  ret void, !dbg !59
}

; Function Attrs: noinline nounwind optnone uwtable
define dso_local ptr @reader(ptr noundef %0) #0 !dbg !60 {
  %2 = alloca ptr, align 8
  store ptr %0, ptr %2, align 8
  call void @llvm.dbg.declare(metadata ptr %2, metadata !61, metadata !DIExpression()), !dbg !62
  %3 = load ptr, ptr %2, align 8, !dbg !63
  call void @observe_data(), !dbg !64
  ret ptr null, !dbg !65
}

; Function Attrs: noinline nounwind optnone uwtable
define internal void @observe_data() #0 !dbg !66 {
  %1 = alloca i32, align 4
  %2 = alloca i32, align 4
  %3 = alloca i32, align 4
  %4 = alloca i32, align 4
  call void @llvm.dbg.declare(metadata ptr %1, metadata !67, metadata !DIExpression()), !dbg !68
  %5 = load atomic i32, ptr @relay_flag acquire, align 4, !dbg !69
  store i32 %5, ptr %2, align 4, !dbg !69
  %6 = load i32, ptr %2, align 4, !dbg !69
  store i32 %6, ptr %1, align 4, !dbg !68
  call void @llvm.dbg.declare(metadata ptr %3, metadata !70, metadata !DIExpression()), !dbg !71
  %7 = load atomic i32, ptr @data monotonic, align 4, !dbg !72
  store i32 %7, ptr %4, align 4, !dbg !72
  %8 = load i32, ptr %4, align 4, !dbg !72
  store i32 %8, ptr %3, align 4, !dbg !71
  %9 = load i32, ptr %1, align 4, !dbg !73
  %10 = load i32, ptr %3, align 4, !dbg !74
  ret void, !dbg !75
}

; Function Attrs: noinline nounwind optnone uwtable
define dso_local i32 @main() #0 !dbg !76 {
  %1 = alloca i32, align 4
  %2 = alloca i64, align 8
  %3 = alloca i64, align 8
  %4 = alloca i64, align 8
  store i32 0, ptr %1, align 4
  call void @llvm.dbg.declare(metadata ptr %2, metadata !79, metadata !DIExpression()), !dbg !83
  call void @llvm.dbg.declare(metadata ptr %3, metadata !84, metadata !DIExpression()), !dbg !85
  call void @llvm.dbg.declare(metadata ptr %4, metadata !86, metadata !DIExpression()), !dbg !87
  %5 = call i32 @pthread_create(ptr noundef %2, ptr noundef null, ptr noundef @writer, ptr noundef null) #4, !dbg !88
  %6 = call i32 @pthread_create(ptr noundef %3, ptr noundef null, ptr noundef @relay, ptr noundef null) #4, !dbg !89
  %7 = call i32 @pthread_create(ptr noundef %4, ptr noundef null, ptr noundef @reader, ptr noundef null) #4, !dbg !90
  %8 = load i64, ptr %2, align 8, !dbg !91
  %9 = call i32 @pthread_join(i64 noundef %8, ptr noundef null), !dbg !92
  %10 = load i64, ptr %3, align 8, !dbg !93
  %11 = call i32 @pthread_join(i64 noundef %10, ptr noundef null), !dbg !94
  %12 = load i64, ptr %4, align 8, !dbg !95
  %13 = call i32 @pthread_join(i64 noundef %12, ptr noundef null), !dbg !96
  ret i32 0, !dbg !97
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
!llvm.module.flags = !{!23, !24, !25, !26, !27, !28, !29}
!llvm.ident = !{!30}

!0 = !DIGlobalVariableExpression(var: !1, expr: !DIExpression())
!1 = distinct !DIGlobalVariable(name: "data", scope: !2, file: !18, line: 4, type: !19, isLocal: false, isDefinition: true)
!2 = distinct !DICompileUnit(language: DW_LANG_C11, file: !3, producer: "Ubuntu clang version 18.1.3 (1ubuntu1)", isOptimized: false, runtimeVersion: 0, emissionKind: FullDebug, enums: !4, globals: !15, splitDebugInlining: false, nameTableKind: None)
!3 = !DIFile(filename: "/home/zhovy/work/Case_Regression_Internal/cases/P03_release_acquire_relay/case.c", directory: "/home/zhovy/work/Case_Regression_Internal", checksumkind: CSK_MD5, checksum: "97fd824d2f724e13ef23075d2647d1c6")
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
!15 = !{!0, !16, !21}
!16 = !DIGlobalVariableExpression(var: !17, expr: !DIExpression())
!17 = distinct !DIGlobalVariable(name: "flag", scope: !2, file: !18, line: 5, type: !19, isLocal: false, isDefinition: true)
!18 = !DIFile(filename: "cases/P03_release_acquire_relay/case.c", directory: "/home/zhovy/work/Case_Regression_Internal", checksumkind: CSK_MD5, checksum: "97fd824d2f724e13ef23075d2647d1c6")
!19 = !DIDerivedType(tag: DW_TAG_atomic_type, baseType: !20)
!20 = !DIBasicType(name: "int", size: 32, encoding: DW_ATE_signed)
!21 = !DIGlobalVariableExpression(var: !22, expr: !DIExpression())
!22 = distinct !DIGlobalVariable(name: "relay_flag", scope: !2, file: !18, line: 6, type: !19, isLocal: false, isDefinition: true)
!23 = !{i32 7, !"Dwarf Version", i32 5}
!24 = !{i32 2, !"Debug Info Version", i32 3}
!25 = !{i32 1, !"wchar_size", i32 4}
!26 = !{i32 8, !"PIC Level", i32 2}
!27 = !{i32 7, !"PIE Level", i32 2}
!28 = !{i32 7, !"uwtable", i32 2}
!29 = !{i32 7, !"frame-pointer", i32 2}
!30 = !{!"Ubuntu clang version 18.1.3 (1ubuntu1)"}
!31 = distinct !DISubprogram(name: "writer", scope: !18, file: !18, line: 25, type: !32, scopeLine: 25, flags: DIFlagPrototyped, spFlags: DISPFlagDefinition, unit: !2, retainedNodes: !35)
!32 = !DISubroutineType(types: !33)
!33 = !{!34, !34}
!34 = !DIDerivedType(tag: DW_TAG_pointer_type, baseType: null, size: 64)
!35 = !{}
!36 = !DILocalVariable(name: "arg", arg: 1, scope: !31, file: !18, line: 25, type: !34)
!37 = !DILocation(line: 25, column: 20, scope: !31)
!38 = !DILocation(line: 26, column: 11, scope: !31)
!39 = !DILocation(line: 27, column: 5, scope: !31)
!40 = !DILocation(line: 28, column: 5, scope: !31)
!41 = distinct !DISubprogram(name: "publish_data", scope: !18, file: !18, line: 8, type: !42, scopeLine: 8, flags: DIFlagPrototyped, spFlags: DISPFlagLocalToUnit | DISPFlagDefinition, unit: !2)
!42 = !DISubroutineType(types: !43)
!43 = !{null}
!44 = !DILocation(line: 9, column: 5, scope: !41)
!45 = !DILocation(line: 10, column: 5, scope: !41)
!46 = !DILocation(line: 11, column: 1, scope: !41)
!47 = distinct !DISubprogram(name: "relay", scope: !18, file: !18, line: 31, type: !32, scopeLine: 31, flags: DIFlagPrototyped, spFlags: DISPFlagDefinition, unit: !2, retainedNodes: !35)
!48 = !DILocalVariable(name: "arg", arg: 1, scope: !47, file: !18, line: 31, type: !34)
!49 = !DILocation(line: 31, column: 19, scope: !47)
!50 = !DILocation(line: 32, column: 11, scope: !47)
!51 = !DILocation(line: 33, column: 5, scope: !47)
!52 = !DILocation(line: 34, column: 5, scope: !47)
!53 = distinct !DISubprogram(name: "relay_once", scope: !18, file: !18, line: 13, type: !42, scopeLine: 13, flags: DIFlagPrototyped, spFlags: DISPFlagLocalToUnit | DISPFlagDefinition, unit: !2, retainedNodes: !35)
!54 = !DILocalVariable(name: "seen", scope: !53, file: !18, line: 14, type: !20)
!55 = !DILocation(line: 14, column: 9, scope: !53)
!56 = !DILocation(line: 14, column: 16, scope: !53)
!57 = !DILocation(line: 15, column: 40, scope: !53)
!58 = !DILocation(line: 15, column: 5, scope: !53)
!59 = !DILocation(line: 16, column: 1, scope: !53)
!60 = distinct !DISubprogram(name: "reader", scope: !18, file: !18, line: 37, type: !32, scopeLine: 37, flags: DIFlagPrototyped, spFlags: DISPFlagDefinition, unit: !2, retainedNodes: !35)
!61 = !DILocalVariable(name: "arg", arg: 1, scope: !60, file: !18, line: 37, type: !34)
!62 = !DILocation(line: 37, column: 20, scope: !60)
!63 = !DILocation(line: 38, column: 11, scope: !60)
!64 = !DILocation(line: 39, column: 5, scope: !60)
!65 = !DILocation(line: 40, column: 5, scope: !60)
!66 = distinct !DISubprogram(name: "observe_data", scope: !18, file: !18, line: 18, type: !42, scopeLine: 18, flags: DIFlagPrototyped, spFlags: DISPFlagLocalToUnit | DISPFlagDefinition, unit: !2, retainedNodes: !35)
!67 = !DILocalVariable(name: "ready", scope: !66, file: !18, line: 19, type: !20)
!68 = !DILocation(line: 19, column: 9, scope: !66)
!69 = !DILocation(line: 19, column: 17, scope: !66)
!70 = !DILocalVariable(name: "payload", scope: !66, file: !18, line: 20, type: !20)
!71 = !DILocation(line: 20, column: 9, scope: !66)
!72 = !DILocation(line: 20, column: 19, scope: !66)
!73 = !DILocation(line: 21, column: 11, scope: !66)
!74 = !DILocation(line: 22, column: 11, scope: !66)
!75 = !DILocation(line: 23, column: 1, scope: !66)
!76 = distinct !DISubprogram(name: "main", scope: !18, file: !18, line: 43, type: !77, scopeLine: 43, flags: DIFlagPrototyped, spFlags: DISPFlagDefinition, unit: !2, retainedNodes: !35)
!77 = !DISubroutineType(types: !78)
!78 = !{!20}
!79 = !DILocalVariable(name: "first", scope: !76, file: !18, line: 44, type: !80)
!80 = !DIDerivedType(tag: DW_TAG_typedef, name: "pthread_t", file: !81, line: 27, baseType: !82)
!81 = !DIFile(filename: "/usr/include/x86_64-linux-gnu/bits/pthreadtypes.h", directory: "", checksumkind: CSK_MD5, checksum: "8a5acdbeec491eca11cf81cb1ef77ea7")
!82 = !DIBasicType(name: "unsigned long", size: 64, encoding: DW_ATE_unsigned)
!83 = !DILocation(line: 44, column: 15, scope: !76)
!84 = !DILocalVariable(name: "second", scope: !76, file: !18, line: 44, type: !80)
!85 = !DILocation(line: 44, column: 22, scope: !76)
!86 = !DILocalVariable(name: "third", scope: !76, file: !18, line: 44, type: !80)
!87 = !DILocation(line: 44, column: 30, scope: !76)
!88 = !DILocation(line: 45, column: 5, scope: !76)
!89 = !DILocation(line: 46, column: 5, scope: !76)
!90 = !DILocation(line: 47, column: 5, scope: !76)
!91 = !DILocation(line: 48, column: 18, scope: !76)
!92 = !DILocation(line: 48, column: 5, scope: !76)
!93 = !DILocation(line: 49, column: 18, scope: !76)
!94 = !DILocation(line: 49, column: 5, scope: !76)
!95 = !DILocation(line: 50, column: 18, scope: !76)
!96 = !DILocation(line: 50, column: 5, scope: !76)
!97 = !DILocation(line: 51, column: 5, scope: !76)
