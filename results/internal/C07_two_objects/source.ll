; ModuleID = '/home/zhovy/work/Case_Regression_Internal/cases/C07_two_objects/case.c'
source_filename = "/home/zhovy/work/Case_Regression_Internal/cases/C07_two_objects/case.c"
target datalayout = "e-m:e-p270:32:32-p271:32:32-p272:64:64-i64:64-i128:128-f80:128-n8:16:32:64-S128"
target triple = "x86_64-pc-linux-gnu"

@data = dso_local global i32 0, align 4, !dbg !0
@flag = dso_local global i32 0, align 4, !dbg !5

; Function Attrs: noinline nounwind optnone uwtable
define dso_local ptr @writer(ptr noundef %0) #0 !dbg !17 {
  %2 = alloca ptr, align 8
  store ptr %0, ptr %2, align 8
  call void @llvm.dbg.declare(metadata ptr %2, metadata !22, metadata !DIExpression()), !dbg !23
  %3 = load ptr, ptr %2, align 8, !dbg !24
  store i32 1, ptr @data, align 4, !dbg !25
  store i32 1, ptr @flag, align 4, !dbg !26
  ret ptr null, !dbg !27
}

; Function Attrs: nocallback nofree nosync nounwind speculatable willreturn memory(none)
declare void @llvm.dbg.declare(metadata, metadata, metadata) #1

; Function Attrs: noinline nounwind optnone uwtable
define dso_local ptr @reader(ptr noundef %0) #0 !dbg !28 {
  %2 = alloca ptr, align 8
  %3 = alloca i32, align 4
  %4 = alloca i32, align 4
  store ptr %0, ptr %2, align 8
  call void @llvm.dbg.declare(metadata ptr %2, metadata !29, metadata !DIExpression()), !dbg !30
  %5 = load ptr, ptr %2, align 8, !dbg !31
  call void @llvm.dbg.declare(metadata ptr %3, metadata !32, metadata !DIExpression()), !dbg !33
  %6 = load i32, ptr @flag, align 4, !dbg !34
  store i32 %6, ptr %3, align 4, !dbg !33
  call void @llvm.dbg.declare(metadata ptr %4, metadata !35, metadata !DIExpression()), !dbg !36
  %7 = load i32, ptr @data, align 4, !dbg !37
  store i32 %7, ptr %4, align 4, !dbg !36
  %8 = load i32, ptr %3, align 4, !dbg !38
  %9 = load i32, ptr %4, align 4, !dbg !39
  ret ptr null, !dbg !40
}

; Function Attrs: noinline nounwind optnone uwtable
define dso_local i32 @main() #0 !dbg !41 {
  %1 = alloca i32, align 4
  %2 = alloca i64, align 8
  %3 = alloca i64, align 8
  store i32 0, ptr %1, align 4
  call void @llvm.dbg.declare(metadata ptr %2, metadata !44, metadata !DIExpression()), !dbg !48
  call void @llvm.dbg.declare(metadata ptr %3, metadata !49, metadata !DIExpression()), !dbg !50
  %4 = call i32 @pthread_create(ptr noundef %2, ptr noundef null, ptr noundef @writer, ptr noundef null) #4, !dbg !51
  %5 = call i32 @pthread_create(ptr noundef %3, ptr noundef null, ptr noundef @reader, ptr noundef null) #4, !dbg !52
  %6 = load i64, ptr %2, align 8, !dbg !53
  %7 = call i32 @pthread_join(i64 noundef %6, ptr noundef null), !dbg !54
  %8 = load i64, ptr %3, align 8, !dbg !55
  %9 = call i32 @pthread_join(i64 noundef %8, ptr noundef null), !dbg !56
  ret i32 0, !dbg !57
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
!llvm.module.flags = !{!9, !10, !11, !12, !13, !14, !15}
!llvm.ident = !{!16}

!0 = !DIGlobalVariableExpression(var: !1, expr: !DIExpression())
!1 = distinct !DIGlobalVariable(name: "data", scope: !2, file: !7, line: 3, type: !8, isLocal: false, isDefinition: true)
!2 = distinct !DICompileUnit(language: DW_LANG_C11, file: !3, producer: "Ubuntu clang version 18.1.3 (1ubuntu1)", isOptimized: false, runtimeVersion: 0, emissionKind: FullDebug, globals: !4, splitDebugInlining: false, nameTableKind: None)
!3 = !DIFile(filename: "/home/zhovy/work/Case_Regression_Internal/cases/C07_two_objects/case.c", directory: "/home/zhovy/work/Case_Regression_Internal", checksumkind: CSK_MD5, checksum: "a6b0d16bb8f3010bd38a725fd97ed48a")
!4 = !{!0, !5}
!5 = !DIGlobalVariableExpression(var: !6, expr: !DIExpression())
!6 = distinct !DIGlobalVariable(name: "flag", scope: !2, file: !7, line: 4, type: !8, isLocal: false, isDefinition: true)
!7 = !DIFile(filename: "cases/C07_two_objects/case.c", directory: "/home/zhovy/work/Case_Regression_Internal", checksumkind: CSK_MD5, checksum: "a6b0d16bb8f3010bd38a725fd97ed48a")
!8 = !DIBasicType(name: "int", size: 32, encoding: DW_ATE_signed)
!9 = !{i32 7, !"Dwarf Version", i32 5}
!10 = !{i32 2, !"Debug Info Version", i32 3}
!11 = !{i32 1, !"wchar_size", i32 4}
!12 = !{i32 8, !"PIC Level", i32 2}
!13 = !{i32 7, !"PIE Level", i32 2}
!14 = !{i32 7, !"uwtable", i32 2}
!15 = !{i32 7, !"frame-pointer", i32 2}
!16 = !{!"Ubuntu clang version 18.1.3 (1ubuntu1)"}
!17 = distinct !DISubprogram(name: "writer", scope: !7, file: !7, line: 6, type: !18, scopeLine: 6, flags: DIFlagPrototyped, spFlags: DISPFlagDefinition, unit: !2, retainedNodes: !21)
!18 = !DISubroutineType(types: !19)
!19 = !{!20, !20}
!20 = !DIDerivedType(tag: DW_TAG_pointer_type, baseType: null, size: 64)
!21 = !{}
!22 = !DILocalVariable(name: "arg", arg: 1, scope: !17, file: !7, line: 6, type: !20)
!23 = !DILocation(line: 6, column: 20, scope: !17)
!24 = !DILocation(line: 7, column: 11, scope: !17)
!25 = !DILocation(line: 8, column: 10, scope: !17)
!26 = !DILocation(line: 9, column: 10, scope: !17)
!27 = !DILocation(line: 10, column: 5, scope: !17)
!28 = distinct !DISubprogram(name: "reader", scope: !7, file: !7, line: 13, type: !18, scopeLine: 13, flags: DIFlagPrototyped, spFlags: DISPFlagDefinition, unit: !2, retainedNodes: !21)
!29 = !DILocalVariable(name: "arg", arg: 1, scope: !28, file: !7, line: 13, type: !20)
!30 = !DILocation(line: 13, column: 20, scope: !28)
!31 = !DILocation(line: 14, column: 11, scope: !28)
!32 = !DILocalVariable(name: "seen_flag", scope: !28, file: !7, line: 15, type: !8)
!33 = !DILocation(line: 15, column: 9, scope: !28)
!34 = !DILocation(line: 15, column: 21, scope: !28)
!35 = !DILocalVariable(name: "seen_data", scope: !28, file: !7, line: 16, type: !8)
!36 = !DILocation(line: 16, column: 9, scope: !28)
!37 = !DILocation(line: 16, column: 21, scope: !28)
!38 = !DILocation(line: 17, column: 11, scope: !28)
!39 = !DILocation(line: 18, column: 11, scope: !28)
!40 = !DILocation(line: 19, column: 5, scope: !28)
!41 = distinct !DISubprogram(name: "main", scope: !7, file: !7, line: 22, type: !42, scopeLine: 22, flags: DIFlagPrototyped, spFlags: DISPFlagDefinition, unit: !2, retainedNodes: !21)
!42 = !DISubroutineType(types: !43)
!43 = !{!8}
!44 = !DILocalVariable(name: "first", scope: !41, file: !7, line: 23, type: !45)
!45 = !DIDerivedType(tag: DW_TAG_typedef, name: "pthread_t", file: !46, line: 27, baseType: !47)
!46 = !DIFile(filename: "/usr/include/x86_64-linux-gnu/bits/pthreadtypes.h", directory: "", checksumkind: CSK_MD5, checksum: "8a5acdbeec491eca11cf81cb1ef77ea7")
!47 = !DIBasicType(name: "unsigned long", size: 64, encoding: DW_ATE_unsigned)
!48 = !DILocation(line: 23, column: 15, scope: !41)
!49 = !DILocalVariable(name: "second", scope: !41, file: !7, line: 23, type: !45)
!50 = !DILocation(line: 23, column: 22, scope: !41)
!51 = !DILocation(line: 24, column: 5, scope: !41)
!52 = !DILocation(line: 25, column: 5, scope: !41)
!53 = !DILocation(line: 26, column: 18, scope: !41)
!54 = !DILocation(line: 26, column: 5, scope: !41)
!55 = !DILocation(line: 27, column: 18, scope: !41)
!56 = !DILocation(line: 27, column: 5, scope: !41)
!57 = !DILocation(line: 28, column: 5, scope: !41)
