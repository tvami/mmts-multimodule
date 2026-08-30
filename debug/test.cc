#include <cstdio>
#include <sys/mman.h>
#include <fcntl.h>
#include <unistd.h>
#include <stdint.h>
#include <stdio.h>
#include <cstdlib>


int main()
{
  int fd_ = open("/dev/uio15", O_RDWR | O_SYNC);
  const unsigned int MAP_SIZE = 0x1000;
  uint32_t* mapbase_=(uint32_t*) (mmap(0,MAP_SIZE,PROT_READ|PROT_WRITE,MAP_SHARED, fd_, 0x0));
  for(int i = 0; i < 32; ++i)
    {
      printf("%i, %x\n", i, mapbase_[i]);
    }
}
