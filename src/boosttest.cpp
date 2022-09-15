#include "test.h"
#include <boost/lexical_cast.hpp>
#include <string>

void dtoa_boost(double value, char* buffer) {
  std::string str = boost::lexical_cast<std::string>(value);
  strcpy(buffer, str.c_str()); 
}

REGISTER_TEST(boost);
