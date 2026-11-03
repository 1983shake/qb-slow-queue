"""qb-slow-queue 版本与发布信息。

版本唯一来源：本文件。Docker 镜像 tag、Compose 镜像名、构建参数、发布说明
的版本标识均由本文件派生，禁止在其它位置另设版本号。

字段说明：
- __version__        : 语义化版本号
- __release_status__ : "test"（测试版）或 "formal"（正式版）
- __test_sequence__  : 测试版每次交付/迭代递增；正式版必须为 0
- __docker_tag__     : 完整镜像引用，测试版含 -test.N 标识，正式版为干净标签
"""

__version__ = "1.0.0"
__release_status__ = "formal"  # test 或 formal
__test_sequence__ = 0  # 测试版递增；正式版归 0
__docker_tag__ = "docker.cnb.cool/1983shake/qb-slow-queue:latest"
